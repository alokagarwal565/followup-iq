"""Deterministic stand-in for Gemini, enabled only by GEMINI_FAKE=1 (refused in production).

It reads simple keywords from the chat so end-to-end tests see realistic tag changes (for example
a quote request turning a lead Hot) without network calls or API cost. Its answer still passes
through the real validator, so E2E runs exercise the same rules and guards as production.
"""

import json
from datetime import date

from app.ai.prompt import PromptContext
from app.ai.provider import AnalysisFailed, ProviderResult, Valid
from app.ai.validation import ValidatedAnalysis, Validator
from app.domain.rules import classify
from app.domain.types import Intent, Signals


def _intent(text: str) -> Intent:
    if "order" in text and ("ready" in text or "confirm" in text or "po " in text):
        return "ready_to_order"
    if "quote" in text or "quotation" in text or "price" in text:
        return "quote_requested"
    if "demo" in text:
        return "demo_requested"
    if text.strip():
        return "inquiry"
    return "none"


def _timeline(text: str) -> int | None:
    for phrase, days in (("this week", 5), ("this month", 20), ("next month", 30), ("3 weeks", 21)):
        if phrase in text:
            return days
    return None


def fake_answer(ctx: PromptContext) -> str:
    recent = " ".join(m.body for m in ctx.messages[-6:]).lower()
    last = ctx.messages[-1] if ctx.messages else None
    dnc = "don't message" in recent or "do not contact" in recent
    disqualified = dnc or "another supplier" in recent or "not interested" in recent
    awaiting = bool(last and last.sender_type == "buyer" and "?" in last.body)
    signals = Signals(
        intent=_intent(recent),
        timeline_days=_timeline(recent),
        evaluating="spec" in recent or "demo" in recent or "compar" in recent,
        objection="price" if "lower" in recent or "discount" in recent else "none",
        disqualified=disqualified,
        do_not_contact=dnc,
        awaiting_our_reply=awaiting,
        commitment_date=None,
        commitment_made_on=None,
    )
    label, _ = classify(signals, ctx.facts, ctx.today)
    first = ctx.buyer_name.split()[0] if ctx.buyer_name.split() else ctx.buyer_name
    draft = (
        ""
        if dnc
        else f"Hi {first}, thanks for your time. Following up on our conversation, could we "
        "fix a quick call this week to take this forward?"
    )
    return json.dumps(
        {
            "intent": signals.intent,
            "timeline_days": signals.timeline_days,
            "evaluating": signals.evaluating,
            "objection": signals.objection,
            "disqualified": signals.disqualified,
            "do_not_contact": signals.do_not_contact,
            "awaiting_our_reply": signals.awaiting_our_reply,
            "commitment_date": None,
            "commitment_quote": None,
            "suggested_label": label,
            "reason": f"Test analysis: classified {label} from keywords in the latest messages.",
            "follow_up_reason": "Follow up on the latest conversation.",
            "draft_message": draft,
            "evidence": [f"Last message: {last.body}"[:100] if last else "No conversation yet"],
        },
        default=date.isoformat,
    )


class FakeAnalyzer:
    async def analyze(
        self, *, context: PromptContext, validate: Validator, lead_id: str
    ) -> ProviderResult[ValidatedAnalysis]:
        outcome = validate(fake_answer(context), "STOP")
        if not isinstance(outcome, Valid):
            raise AnalysisFailed("malformed_output", attempts=1)
        return ProviderResult(outcome.value, model="fake", key_slot=0, attempts=1)
