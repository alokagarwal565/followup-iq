"""Turns raw model text into a rule-checked analysis, or a precise problem for the re-ask."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from pydantic import ValidationError

from app.ai.guards import (
    check_consistency,
    check_do_not_contact,
    check_invented_commitments,
    locate_commitment,
)
from app.ai.prompt import PromptContext
from app.ai.provider import Invalid, Valid
from app.ai.schema import LeadAnalysisOut
from app.domain.rules import classify, next_follow_up
from app.domain.types import FollowUpReason, Label, RuleId, Signals
from app.logging import get_logger

log = get_logger("ai.validation")

_SAFETY_STOPS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


@dataclass(frozen=True)
class ValidatedAnalysis:
    out: LeadAnalysisOut
    signals: Signals
    label: Label
    rule_id: RuleId
    follow_up: date | None
    follow_up_basis: FollowUpReason


Validator = Callable[[str, str | None], Valid[ValidatedAnalysis] | Invalid]


def _describe(exc: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(p) for p in err['loc']) or 'response'}: {err['msg']}"
        for err in exc.errors()[:8]
    ]
    return "The JSON did not match the schema: " + "; ".join(parts)


def make_validator(ctx: PromptContext) -> Validator:
    conversation = "\n".join(m.body for m in ctx.messages)

    def validate(text: str, finish_reason: str | None) -> Valid[ValidatedAnalysis] | Invalid:
        if not text.strip():
            if finish_reason in _SAFETY_STOPS:
                return Invalid(
                    "safety_blocked", "The answer was blocked; analyse the sales facts only."
                )
            return Invalid("malformed_output", "The answer was empty; return the JSON object.")
        try:
            out = LeadAnalysisOut.model_validate_json(text)
        except ValidationError as exc:
            return Invalid("malformed_output", _describe(exc))

        made_on = None
        if out.commitment_date is not None:
            made_on = locate_commitment(out.commitment_quote, ctx.messages, ctx.tz)
            if made_on is None:
                # The quote must appear in the chat; otherwise the commitment may be invented.
                log.warning("commitment_quote_not_found")
        signals = Signals(
            intent=out.intent,
            timeline_days=out.timeline_days,
            evaluating=out.evaluating,
            objection=out.objection,
            disqualified=out.disqualified,
            do_not_contact=out.do_not_contact,
            awaiting_our_reply=out.awaiting_our_reply,
            commitment_date=out.commitment_date if made_on else None,
            commitment_made_on=made_on,
        )
        label, rule_id = classify(signals, ctx.facts, ctx.today)

        candidates = [
            check_consistency(out, rule_label=label, rule_id=rule_id),
            check_do_not_contact(out),
            *check_invented_commitments(out.draft_message, conversation),
        ]
        problems = [p for p in candidates if p]
        if problems:
            return Invalid("malformed_output", " ".join(problems))

        follow_up, basis = next_follow_up(label, rule_id, signals, ctx.facts, ctx.today)
        return Valid(ValidatedAnalysis(out, signals, label, rule_id, follow_up, basis))

    return validate
