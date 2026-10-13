from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection

from app.db.queries import drafts as draft_q
from app.db.queries import leads as lead_q
from app.db.queries import messages as message_q
from app.db.queries.leads import NewLeadRow
from app.db.records import DraftRecord, LeadRecord, MessageRecord
from app.domain.phone import phone_digits
from app.domain.rules import QueueEntry, due_state, queue_sort_key
from app.domain.types import DueState
from app.errors import ConflictError, UnprocessableError, lead_not_found

# Clocks on reps' phones drift; a few minutes of "future" is tolerated rather than rejected.
FUTURE_TOLERANCE = timedelta(minutes=5)
MAX_BACKDATE = timedelta(days=365)
# Date-only contact dates are stored at local midday so no timezone conversion can move the day.
_MIDDAY = time(12, 0)


@dataclass(frozen=True)
class NewMessage:
    sender_type: str
    body: str
    sent_at: datetime | None


@dataclass(frozen=True)
class NewLead:
    name: str
    company: str
    phone: str
    source: str
    assigned_rep: str
    last_contact_date: date | None
    messages: list[NewMessage] = field(default_factory=list)
    request_id: UUID | None = None


@dataclass(frozen=True)
class LeadDetail:
    lead: LeadRecord
    messages: list[MessageRecord]
    draft: DraftRecord


def duplicate_phone(existing: UUID) -> ConflictError:
    return ConflictError(
        "A lead with this phone number already exists",
        code="duplicate_phone",
        details={"existing_lead_id": str(existing)},
    )


def _resolve_times(items: list[NewMessage], now: datetime, floor: datetime) -> list[datetime]:
    resolved = []
    count = len(items)
    for index, item in enumerate(items):
        # Untimed messages are spaced a second apart, ending now, so entry order is preserved.
        sent_at = item.sent_at or now - timedelta(seconds=count - 1 - index)
        if sent_at > now + FUTURE_TOLERANCE:
            raise UnprocessableError("Message time is in the future", code="sent_at_in_future")
        if sent_at < floor:
            raise UnprocessableError("Message time is more than a year old", code="sent_at_too_old")
        resolved.append(sent_at.astimezone(UTC))
    return resolved


async def _append_messages(
    conn: AsyncConnection,
    lead_id: UUID,
    items: list[NewMessage],
    times: list[datetime],
    request_id: UUID | None,
) -> None:
    conversation_id = await message_q.ensure_conversation(conn, lead_id)
    for item, sent_at in zip(items, times, strict=True):
        await message_q.insert(
            conn, conversation_id, item.sender_type, item.body, sent_at, request_id=request_id
        )


async def create_lead(
    conn: AsyncConnection, data: NewLead, *, now: datetime, tz: ZoneInfo
) -> tuple[UUID, bool]:
    """Returns (lead id, created). A replayed request id returns the original lead uncreated."""
    async with conn.transaction():
        if data.request_id is not None:
            await message_q.lock_request(conn, data.request_id)
            existing = await message_q.lead_for_request(conn, data.request_id)
            if existing is not None:
                return existing, False

        digits = phone_digits(data.phone)
        clash = await lead_q.find_by_phone_digits(conn, digits)
        if clash is not None:
            raise duplicate_phone(clash)

        today = now.astimezone(tz).date()
        contact_at: datetime | None = None
        if data.last_contact_date is not None:
            if data.last_contact_date > today:
                raise UnprocessableError(
                    "Last contact date cannot be in the future", code="last_contact_in_future"
                )
            contact_at = datetime.combine(data.last_contact_date, _MIDDAY, tzinfo=tz).astimezone(
                UTC
            )

        times = _resolve_times(data.messages, now, now - MAX_BACKDATE)
        if times:
            contact_at = max([*times, *([contact_at] if contact_at else [])])

        lead_id = await lead_q.insert(
            conn,
            NewLeadRow(
                name=data.name,
                company=data.company,
                phone=data.phone,
                phone_digits=digits,
                source=data.source,
                assigned_rep=data.assigned_rep,
                last_contact_at=contact_at,
            ),
            created_at=now,
        )
        await draft_q.create(conn, lead_id)
        if data.messages:
            await _append_messages(conn, lead_id, data.messages, times, data.request_id)
        await lead_q.update(conn, lead_id, analysis_status="pending", analysis_requested_at=now)
    return lead_id, True


async def add_messages(
    conn: AsyncConnection,
    lead_id: UUID,
    items: list[NewMessage],
    *,
    request_id: UUID,
    now: datetime,
) -> bool:
    """Persists messages before any analysis runs. Returns False when the request was a replay."""
    async with conn.transaction():
        lead = await lead_q.get(conn, lead_id, for_update=True)
        if lead is None:
            raise lead_not_found()
        await message_q.lock_request(conn, request_id)
        if await message_q.lead_for_request(conn, request_id) is not None:
            return False
        times = _resolve_times(items, now, lead.created_at - MAX_BACKDATE)
        await _append_messages(conn, lead_id, items, times, request_id)
        newest = max(times)
        await lead_q.update(
            conn,
            lead_id,
            last_contact_at=max(newest, lead.last_contact_at) if lead.last_contact_at else newest,
            analysis_status="pending",
            analysis_requested_at=now,
        )
    return True


async def update_lead(conn: AsyncConnection, lead_id: UUID, changes: dict[str, Any]) -> None:
    async with conn.transaction():
        lead = await lead_q.get(conn, lead_id, for_update=True)
        if lead is None:
            raise lead_not_found()
        if "phone" in changes:
            digits = phone_digits(changes["phone"])
            clash = await lead_q.find_by_phone_digits(conn, digits)
            if clash is not None and clash != lead_id:
                raise duplicate_phone(clash)
            changes = {**changes, "phone_digits": digits}
        await lead_q.update(conn, lead_id, **changes)


async def request_analysis(conn: AsyncConnection, lead_id: UUID, *, now: datetime) -> None:
    async with conn.transaction():
        if await lead_q.get(conn, lead_id, for_update=True) is None:
            raise lead_not_found()
        await lead_q.update(conn, lead_id, analysis_status="pending", analysis_requested_at=now)


async def get_detail(conn: AsyncConnection, lead_id: UUID) -> LeadDetail:
    lead = await lead_q.get(conn, lead_id)
    if lead is None:
        raise lead_not_found()
    draft = await draft_q.get(conn, lead_id)
    if draft is None:
        # Leads always get a draft row on creation; this repairs rows inserted outside the app.
        await draft_q.create(conn, lead_id)
        draft = await draft_q.get(conn, lead_id)
    assert draft is not None
    return LeadDetail(lead=lead, messages=await message_q.for_lead(conn, lead_id), draft=draft)


def _entry(lead: LeadRecord) -> QueueEntry:
    return QueueEntry(
        id=str(lead.id),
        follow_up=lead.next_follow_up_date,
        label=lead.classification,  # type: ignore[arg-type]
        awaiting_reply=lead.awaiting_our_reply,
        last_contact=lead.last_contact_at,
    )


async def queue(
    conn: AsyncConnection,
    *,
    today: date,
    rep: str | None = None,
    classification: str | None = None,
    q: str | None = None,
    due: DueState | None = None,
) -> list[LeadRecord]:
    leads = await lead_q.list_leads(conn, rep=rep, classification=classification, q=q)
    if due is not None:
        leads = [lead for lead in leads if due_state(lead.next_follow_up_date, today) == due]
    return sorted(leads, key=lambda lead: queue_sort_key(_entry(lead), today))


async def summary(conn: AsyncConnection, *, today: date, rep: str | None) -> dict[str, int]:
    leads = await lead_q.list_leads(conn, rep=rep)
    states = [due_state(lead.next_follow_up_date, today) for lead in leads]
    return {
        "overdue": states.count("overdue"),
        "today": states.count("today"),
        "hot": sum(lead.classification == "Hot" for lead in leads),
        "active": sum(not lead.do_not_contact for lead in leads),
    }
