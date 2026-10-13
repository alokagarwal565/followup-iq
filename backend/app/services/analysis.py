"""The lead follow-up agent: read the lead and chat, ask Gemini, apply the rules, save.

The Gemini call happens with no transaction or lock held (it can take tens of seconds). The write
then re-locks the lead and checks the conversation fingerprint: if a message arrived meanwhile,
the result describes a stale chat and is discarded, because the analysis triggered by that newer
message will write instead.
"""

import hashlib
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import BackgroundTasks
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.ai.analyzer import Analyzer
from app.ai.fallback import rules_only_analysis
from app.ai.prompt import PromptContext, PromptMessage
from app.ai.provider import AnalysisFailed
from app.ai.validation import ValidatedAnalysis, make_validator
from app.config import Settings
from app.db.queries import drafts as draft_q
from app.db.queries import leads as lead_q
from app.db.queries import messages as message_q
from app.db.records import LeadRecord, MessageRecord
from app.domain.facts import MessageView, compute_facts
from app.domain.rules import business_today
from app.logging import get_logger

log = get_logger("services.analysis")

Outcome = Literal["written", "skipped", "superseded", "failed", "fallback", "missing"]


def fingerprint(messages: list[MessageRecord]) -> str:
    digest = hashlib.sha256()
    for message in messages:
        digest.update(f"{message.id}:{message.sender_type}:{message.body}\n".encode())
    return digest.hexdigest()


def _jsonable(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in values.items()}


async def _write_draft(conn: AsyncConnection, lead_id: UUID, *, body: str, dnc: bool) -> None:
    draft = await draft_q.get(conn, lead_id, for_update=True)
    if draft is None:
        await draft_q.create(conn, lead_id)
        draft = await draft_q.get(conn, lead_id, for_update=True)
    assert draft is not None
    if dnc:
        await draft_q.update(conn, lead_id, body="", status="none", suggested_body=None)
    elif draft.status == "edited":
        # Never overwrite the rep's own words; the UI offers the new text as a suggestion.
        await draft_q.update(conn, lead_id, suggested_body=body)
    else:
        await draft_q.update(conn, lead_id, body=body, status="suggested", suggested_body=None)


async def _lock_if_current(
    conn: AsyncConnection, lead_id: UUID, expected: str
) -> LeadRecord | None:
    lead = await lead_q.get(conn, lead_id, for_update=True)
    if lead is None:
        return None
    if fingerprint(await message_q.for_lead(conn, lead_id)) != expected:
        log.info("analysis_superseded", lead_id=str(lead_id))
        return None
    return lead


async def analyze_lead(
    pool: AsyncConnectionPool,
    lead_id: UUID,
    *,
    analyzer: Analyzer,
    settings: Settings,
    now: Callable[[], datetime],
    force: bool = False,
) -> Outcome:
    tz = settings.tz
    async with pool.connection() as conn:
        lead = await lead_q.get(conn, lead_id)
        if lead is None:
            log.warning("analysis_lead_missing", lead_id=str(lead_id))
            return "missing"
        messages = await message_q.for_lead(conn, lead_id)
        current = fingerprint(messages)
        unchanged = (
            lead.analysis_fingerprint == current
            and lead.analysis_source == "gemini"
            and lead.analysis_updated_at is not None
        )
        if unchanged and not force:
            # Nothing new to read; skipping saves quota on duplicate triggers.
            await lead_q.update(conn, lead_id, analysis_status="ok", analysis_error=None)
            log.info("analysis_skipped_unchanged", lead_id=str(lead_id))
            return "skipped"

    today = business_today(tz, now())
    facts = compute_facts(
        [MessageView(m.sender_type, m.sent_at, m.created_at) for m in messages],  # type: ignore[arg-type]
        created_at=lead.created_at,
        last_contact_at=lead.last_contact_at,
        tz=tz,
        today=today,
    )
    context = PromptContext(
        today=today,
        tz=tz,
        rep_name=lead.assigned_rep,
        buyer_name=lead.name,
        company=lead.company,
        source=lead.source,
        facts=facts,
        messages=[PromptMessage(m.sender_type, m.sent_at, m.body) for m in messages],  # type: ignore[arg-type]
    )

    try:
        result = await analyzer.analyze(
            context=context, validate=make_validator(context), lead_id=str(lead_id)
        )
    except AnalysisFailed as failure:
        return await _record_failure(pool, lead_id, current, failure.category, facts, today, now)

    analysis: ValidatedAnalysis = result.value
    async with pool.connection() as conn, conn.transaction():
        locked = await _lock_if_current(conn, lead_id, current)
        if locked is None:
            return "superseded"
        out = analysis.out
        signals = {
            **_jsonable(asdict(analysis.signals)),
            "rule_id": analysis.rule_id,
            "follow_up_basis": analysis.follow_up_basis,
            "suggested_label": out.suggested_label,
            "commitment_quote": out.commitment_quote if analysis.signals.commitment_date else None,
        }
        dnc = analysis.signals.do_not_contact or locked.do_not_contact
        await lead_q.update(
            conn,
            lead_id,
            classification=analysis.label,
            classification_reason=out.reason,
            next_follow_up_date=None if dnc else analysis.follow_up,
            follow_up_reason=out.follow_up_reason,
            evidence=list(out.evidence),
            signals=signals,
            do_not_contact=dnc,
            analysis_status="ok",
            analysis_source="gemini",
            analysis_model=result.model,
            analysis_error=None,
            analysis_updated_at=now(),
            analysis_fingerprint=current,
        )
        await _write_draft(conn, lead_id, body=out.draft_message, dnc=dnc)
    log.info(
        "analysis_written",
        lead_id=str(lead_id),
        label=analysis.label,
        rule_id=analysis.rule_id,
        model=result.model,
        key_slot=result.key_slot,
        attempts=result.attempts,
    )
    return "written"


async def _record_failure(
    pool: AsyncConnectionPool,
    lead_id: UUID,
    current: str,
    category: str,
    facts: Any,
    today: date,
    now: Callable[[], datetime],
) -> Outcome:
    async with pool.connection() as conn, conn.transaction():
        lead = await _lock_if_current(conn, lead_id, current)
        if lead is None:
            return "superseded"
        if lead.analysis_source == "gemini":
            # Keep the last real analysis on screen; the UI shows the failure next to it.
            await lead_q.update(conn, lead_id, analysis_status="failed", analysis_error=category)
            log.warning("analysis_failed_kept_previous", lead_id=str(lead_id), category=category)
            return "failed"
        fallback = rules_only_analysis(buyer_name=lead.name, facts=facts, today=today)
        await lead_q.update(
            conn,
            lead_id,
            classification=fallback.label,
            classification_reason=fallback.reason,
            next_follow_up_date=None if lead.do_not_contact else fallback.follow_up,
            follow_up_reason=fallback.follow_up_reason,
            evidence=[],
            signals={"rule_id": fallback.rule_id, "follow_up_basis": fallback.follow_up_basis},
            analysis_status="failed",
            analysis_source="rules_fallback",
            analysis_model=None,
            analysis_error=category,
            analysis_updated_at=now(),
            analysis_fingerprint=current,
        )
        await _write_draft(conn, lead_id, body=fallback.draft, dnc=lead.do_not_contact)
    log.warning("analysis_rules_fallback", lead_id=str(lead_id), category=category)
    return "fallback"


async def run_analysis_task(
    get_pool: Callable[[], AsyncConnectionPool],
    lead_id: UUID,
    *,
    analyzer: Analyzer,
    settings: Settings,
    now: Callable[[], datetime],
    force: bool = False,
) -> None:
    """BackgroundTasks entry point. A second safety net: an unexpected error must never leave
    the lead stuck on "Updating…", because FastAPI would only print an unlabelled traceback."""
    try:
        await analyze_lead(
            get_pool(), lead_id, analyzer=analyzer, settings=settings, now=now, force=force
        )
    except Exception as exc:
        log.error("analysis_task_failed", lead_id=str(lead_id), exc_type=type(exc).__name__)
        try:
            async with get_pool().connection() as conn:
                await lead_q.update(
                    conn, lead_id, analysis_status="failed", analysis_error="internal"
                )
        except Exception as mark_exc:
            log.error(
                "analysis_mark_failed_failed",
                lead_id=str(lead_id),
                exc_type=type(mark_exc).__name__,
            )


def make_scheduler(
    get_pool: Callable[[], AsyncConnectionPool],
    analyzer: Analyzer,
    settings: Settings,
    now: Callable[[], datetime],
) -> Callable[..., None]:
    def schedule(background: BackgroundTasks, lead_id: UUID, *, force: bool = False) -> None:
        background.add_task(
            run_analysis_task,
            get_pool,
            lead_id,
            analyzer=analyzer,
            settings=settings,
            now=now,
            force=force,
        )

    return schedule
