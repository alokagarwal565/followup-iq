import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.ai.prompt import PromptContext
from app.ai.provider import AnalysisFailed, ProviderResult, Valid
from app.ai.validation import ValidatedAnalysis, Validator
from app.db.queries import drafts as draft_q
from app.db.queries import leads as lead_q
from app.db.queries import messages as message_q
from app.services import analysis
from app.services.leads import NewLead, NewMessage, create_lead
from tests.ai.test_schema import VALID
from tests.api.conftest import make_settings

pytestmark = pytest.mark.asyncio(loop_scope="session")

NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)
SETTINGS = make_settings()


class ScriptedAnalyzer:
    """Answers with a fixed JSON payload through the real validator, or fails on demand."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        fail: str | None = None,
        crash: bool = False,
        during: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.payload = payload
        self.fail = fail
        self.crash = crash
        self.during = during
        self.calls = 0

    async def analyze(
        self, *, context: PromptContext, validate: Validator, lead_id: str
    ) -> ProviderResult[ValidatedAnalysis]:
        self.calls += 1
        if self.during is not None:
            await self.during()
        if self.crash:
            raise RuntimeError("unexpected")
        if self.fail:
            raise AnalysisFailed(self.fail, attempts=3)  # type: ignore[arg-type]
        outcome = validate(json.dumps(self.payload), "STOP")
        assert isinstance(outcome, Valid), outcome
        return ProviderResult(outcome.value, model="test-model", key_slot=1, attempts=1)


def hot_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        **VALID,
        "commitment_date": None,
        "commitment_quote": None,
        "awaiting_our_reply": False,
        "draft_message": "Hi Rahul, sharing the quotation for both pouch fillers today.",
    }
    payload.update(overrides)
    return payload


async def make_lead(pool, *, phone: str = "+91 90000 05001") -> UUID:
    async with pool.connection() as conn:
        lead_id, _ = await create_lead(
            conn,
            NewLead(
                name="Rahul Mehta",
                company="Shree Snacks",
                phone=phone,
                source="IndiaMART",
                assigned_rep="Priya Sharma",
                last_contact_date=None,
                messages=[
                    NewMessage(
                        "buyer",
                        "Need a quote for 2 fillers, order this month",
                        NOW - timedelta(days=2),
                    ),
                    NewMessage(
                        "rep", "Will share it shortly", NOW - timedelta(days=2) + timedelta(hours=1)
                    ),
                ],
            ),
            now=NOW,
            tz=SETTINGS.tz,
        )
    return lead_id


async def run(pool, lead_id: UUID, analyzer, *, force: bool = False):
    return await analysis.analyze_lead(
        pool, lead_id, analyzer=analyzer, settings=SETTINGS, now=lambda: NOW, force=force
    )


async def lead_and_draft(pool, lead_id: UUID):
    async with pool.connection() as conn:
        return await lead_q.get(conn, lead_id), await draft_q.get(conn, lead_id)


async def test_successful_analysis_writes_tag_date_reason_and_draft(pool, clean_db):
    lead_id = await make_lead(pool)
    outcome = await run(pool, lead_id, ScriptedAnalyzer(hot_payload()))
    lead, draft = await lead_and_draft(pool, lead_id)
    assert outcome == "written"
    assert (lead.classification, lead.rule_id) == ("Hot", "H1")
    assert lead.analysis_status == "ok" and lead.analysis_source == "gemini"
    assert lead.analysis_model == "test-model"
    # Hot cadence (last contact + 1) would be yesterday, but the lead was only added today and a
    # follow-up is never scheduled before the lead existed.
    assert lead.next_follow_up_date == NOW.date()
    assert lead.evidence and lead.analysis_fingerprint
    assert (draft.status, draft.body) == ("suggested", hot_payload()["draft_message"])


async def test_rep_edited_draft_is_kept_and_new_text_is_offered(pool, clean_db):
    lead_id = await make_lead(pool)
    async with pool.connection() as conn:
        await draft_q.update(conn, lead_id, body="My own words", status="edited")
    await run(pool, lead_id, ScriptedAnalyzer(hot_payload()))
    _, draft = await lead_and_draft(pool, lead_id)
    assert (draft.body, draft.status) == ("My own words", "edited")
    assert draft.suggested_body == hot_payload()["draft_message"]


async def test_unchanged_conversation_skips_the_model(pool, clean_db):
    lead_id = await make_lead(pool)
    await run(pool, lead_id, ScriptedAnalyzer(hot_payload()))
    async with pool.connection() as conn:
        await lead_q.update(conn, lead_id, analysis_status="pending")
    second = ScriptedAnalyzer(hot_payload())
    assert await run(pool, lead_id, second) == "skipped"
    assert second.calls == 0
    lead, _ = await lead_and_draft(pool, lead_id)
    assert lead.analysis_status == "ok"


async def test_force_reruns_even_when_unchanged(pool, clean_db):
    lead_id = await make_lead(pool)
    await run(pool, lead_id, ScriptedAnalyzer(hot_payload()))
    forced = ScriptedAnalyzer(hot_payload())
    assert await run(pool, lead_id, forced, force=True) == "written"
    assert forced.calls == 1


async def test_result_is_discarded_when_a_message_arrives_mid_analysis(pool, clean_db):
    lead_id = await make_lead(pool)

    async def buyer_writes_again() -> None:
        async with pool.connection() as conn:
            conv = await message_q.ensure_conversation(conn, lead_id)
            await message_q.insert(conn, conv, "buyer", "Also need a sealer", NOW)

    outcome = await run(pool, lead_id, ScriptedAnalyzer(hot_payload(), during=buyer_writes_again))
    lead, _ = await lead_and_draft(pool, lead_id)
    assert outcome == "superseded"
    assert lead.classification is None
    assert lead.analysis_status == "pending"


async def test_failure_keeps_the_previous_good_analysis(pool, clean_db):
    lead_id = await make_lead(pool)
    await run(pool, lead_id, ScriptedAnalyzer(hot_payload()))
    async with pool.connection() as conn:
        conv = await message_q.ensure_conversation(conn, lead_id)
        await message_q.insert(conn, conv, "buyer", "Any update?", NOW)
    outcome = await run(pool, lead_id, ScriptedAnalyzer(fail="exhausted"))
    lead, draft = await lead_and_draft(pool, lead_id)
    assert outcome == "failed"
    assert (lead.classification, lead.analysis_source) == ("Hot", "gemini")
    assert (lead.analysis_status, lead.analysis_error) == ("failed", "exhausted")
    assert draft.body == hot_payload()["draft_message"]


async def test_first_failure_writes_a_labelled_rules_fallback(pool, clean_db):
    lead_id = await make_lead(pool)
    outcome = await run(pool, lead_id, ScriptedAnalyzer(fail="unconfigured"))
    lead, draft = await lead_and_draft(pool, lead_id)
    assert outcome == "fallback"
    assert lead.analysis_source == "rules_fallback"
    assert (lead.analysis_status, lead.analysis_error) == ("failed", "unconfigured")
    assert lead.classification in {"Warm", "Cold"}  # signals unknown, so never Hot
    assert lead.classification_reason.startswith("Rule-based:")
    assert lead.next_follow_up_date is not None
    assert draft.status == "suggested" and draft.body.startswith("Hi Rahul")


async def test_background_task_never_leaves_a_lead_pending(pool, clean_db):
    lead_id = await make_lead(pool)
    await analysis.run_analysis_task(
        lambda: pool,
        lead_id,
        analyzer=ScriptedAnalyzer(crash=True),
        settings=SETTINGS,
        now=lambda: NOW,
    )
    lead, _ = await lead_and_draft(pool, lead_id)
    assert (lead.analysis_status, lead.analysis_error) == ("failed", "internal")


async def test_do_not_contact_clears_the_draft_and_the_date(pool, clean_db):
    lead_id = await make_lead(pool)
    payload = hot_payload(
        intent="none",
        timeline_days=None,
        evaluating=False,
        do_not_contact=True,
        disqualified=True,
        suggested_label="Cold",
        draft_message="",
        reason="Buyer asked not to be contacted again.",
    )
    await run(pool, lead_id, ScriptedAnalyzer(payload))
    lead, draft = await lead_and_draft(pool, lead_id)
    assert (lead.classification, lead.do_not_contact, lead.next_follow_up_date) == (
        "Cold",
        True,
        None,
    )
    assert (draft.status, draft.body) == ("none", "")


async def test_missing_lead_is_a_logged_no_op(pool, clean_db):
    from uuid import uuid4

    assert await run(pool, uuid4(), ScriptedAnalyzer(hot_payload())) == "missing"
