"""Draft state transitions. Every rep write carries the version it was based on (optimistic
concurrency); AI writes go through services.analysis and never overwrite an edited draft."""

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection

from app.db.queries import drafts as draft_q
from app.db.queries import leads as lead_q
from app.db.queries import messages as message_q
from app.db.records import DraftRecord, LeadRecord
from app.domain.rules import next_follow_up
from app.domain.types import Facts, Label, RuleId, Signals
from app.errors import ConflictError, UnprocessableError, lead_not_found

UNDO_WINDOW = timedelta(minutes=10)

# Lead fields a send changes; undo restores exactly these from the snapshot.
_LEAD_SNAPSHOT_FIELDS = (
    "last_contact_at",
    "next_follow_up_date",
    "follow_up_reason",
    "classification",
    "classification_reason",
    "evidence",
    "signals",
    "analysis_status",
    "analysis_source",
    "analysis_model",
    "analysis_error",
    "analysis_requested_at",
    "analysis_updated_at",
    "analysis_fingerprint",
)
_DATETIME_FIELDS = {"last_contact_at", "analysis_requested_at", "analysis_updated_at"}


def version_conflict() -> ConflictError:
    return ConflictError("This draft changed since you opened it", code="version_conflict")


async def _locked(conn: AsyncConnection, lead_id: UUID) -> tuple[LeadRecord, DraftRecord]:
    lead = await lead_q.get(conn, lead_id, for_update=True)
    if lead is None:
        raise lead_not_found()
    draft = await draft_q.get(conn, lead_id, for_update=True)
    if draft is None:
        await draft_q.create(conn, lead_id)
        draft = await draft_q.get(conn, lead_id, for_update=True)
    assert draft is not None
    return lead, draft


async def save(conn: AsyncConnection, lead_id: UUID, *, body: str, version: int) -> None:
    async with conn.transaction():
        lead, draft = await _locked(conn, lead_id)
        if lead.do_not_contact:
            raise UnprocessableError("This buyer asked not to be contacted", code="do_not_contact")
        if draft.version != version:
            raise version_conflict()
        # A rep edit supersedes any held suggestion, and undo would otherwise clobber the edit.
        await draft_q.update(
            conn, lead_id, body=body, status="edited", suggested_body=None, undo_snapshot=None
        )


async def accept_suggestion(conn: AsyncConnection, lead_id: UUID, *, version: int) -> None:
    async with conn.transaction():
        _, draft = await _locked(conn, lead_id)
        if draft.version != version:
            raise version_conflict()
        if not draft.suggested_body:
            raise UnprocessableError("There is no new suggestion", code="no_suggestion")
        await draft_q.update(
            conn,
            lead_id,
            body=draft.suggested_body,
            status="suggested",
            suggested_body=None,
            undo_snapshot=None,
        )


def _cadence_after_contact(lead: LeadRecord, today: date, tz: ZoneInfo) -> date | None:
    label: Label = lead.classification or "Warm"  # type: ignore[assignment]
    rule_id: RuleId = lead.rule_id or ("W1" if label != "Cold" else "C2")  # type: ignore[assignment]
    facts = Facts(
        has_conversation=True,
        last_sender="rep",
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        unanswered_rep_messages=1,
        last_contact_date=today,
        created_date=lead.created_at.astimezone(tz).date(),
    )
    follow_up, _ = next_follow_up(label, rule_id, Signals.unknown(), facts, today)
    return follow_up


def _snapshot(
    lead: LeadRecord, draft: DraftRecord, message_id: UUID, now: datetime
) -> dict[str, Any]:
    lead_values: dict[str, Any] = {}
    for name in _LEAD_SNAPSHOT_FIELDS:
        value = getattr(lead, name)
        lead_values[name] = value.isoformat() if isinstance(value, datetime | date) else value
    return {
        "message_id": str(message_id),
        "sent_at": now.isoformat(),
        "lead": lead_values,
        "draft": {
            "body": draft.body,
            "status": draft.status,
            "suggested_body": draft.suggested_body,
        },
    }


async def send(
    conn: AsyncConnection, lead_id: UUID, *, body: str, version: int, now: datetime, tz: ZoneInfo
) -> bool:
    """Records the message as sent (nothing leaves the app). Returns False for a replayed send."""
    async with conn.transaction():
        lead, draft = await _locked(conn, lead_id)
        if lead.do_not_contact:
            raise UnprocessableError("This buyer asked not to be contacted", code="do_not_contact")
        if draft.version != version:
            if draft.status == "sent" and draft.body == body:
                return False
            raise version_conflict()

        conversation_id = await message_q.ensure_conversation(conn, lead_id)
        message_id = await message_q.insert(
            conn, conversation_id, "rep", body, now, origin="draft_sent"
        )
        await draft_q.update(
            conn,
            lead_id,
            body=body,
            status="sent",
            sent_at=now,
            suggested_body=None,
            undo_snapshot=_snapshot(lead, draft, message_id, now),
        )
        # Rescheduled from the rules now, so the lead leaves Overdue/Today even if AI is down;
        # the follow-up analysis can still refine the date and draft.
        today = now.astimezone(tz).date()
        await lead_q.update(
            conn,
            lead_id,
            last_contact_at=now,
            next_follow_up_date=_cadence_after_contact(lead, today, tz),
            follow_up_reason="Follow up after the message marked as sent.",
            analysis_status="pending",
            analysis_requested_at=now,
        )
    return True


def can_undo(draft: DraftRecord, now: datetime) -> bool:
    snapshot = draft.undo_snapshot
    if not snapshot:
        return False
    return now - datetime.fromisoformat(snapshot["sent_at"]) <= UNDO_WINDOW


async def undo_send(conn: AsyncConnection, lead_id: UUID, *, now: datetime) -> None:
    async with conn.transaction():
        _, draft = await _locked(conn, lead_id)
        snapshot = draft.undo_snapshot
        nothing = ConflictError("There is nothing to undo", code="nothing_to_undo")
        if not snapshot or not can_undo(draft, now):
            raise nothing
        messages = await message_q.for_lead(conn, lead_id)
        # Undo would rewrite history if anything was logged after the send, so it is refused.
        if not messages or str(messages[-1].id) != snapshot["message_id"]:
            raise nothing

        await message_q.delete(conn, UUID(snapshot["message_id"]))
        restored: dict[str, Any] = {}
        for name, value in snapshot["lead"].items():
            if value is not None and name in _DATETIME_FIELDS:
                value = datetime.fromisoformat(value)
            elif value is not None and name == "next_follow_up_date":
                value = date.fromisoformat(value)
            restored[name] = value
        await lead_q.update(conn, lead_id, **restored)
        previous = snapshot["draft"]
        await draft_q.update(
            conn,
            lead_id,
            body=previous["body"],
            status=previous["status"],
            suggested_body=previous["suggested_body"],
            sent_at=None,
            undo_snapshot=None,
        )
