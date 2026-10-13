"""Rule-only analysis used when Gemini is unavailable and the lead has never been analysed.

It is always stored as analysis_source='rules_fallback' and shown as "Rule-based (AI
unavailable)", so it is never mistaken for model output. Signals are unknown here, so a lead
can never become Hot through this path.
"""

from dataclasses import dataclass
from datetime import date

from app.domain.constants import RULE_DESCRIPTIONS
from app.domain.rules import classify, next_follow_up
from app.domain.types import Facts, FollowUpReason, Label, RuleId, Signals

_FOLLOW_UP_REASONS: dict[FollowUpReason, str] = {
    "first_touch": "First contact has not been made yet.",
    "cadence": "Routine follow-up based on the time since last contact.",
    "awaiting_reply": "The buyer is waiting for a reply.",
    "commitment": "A follow-up was promised for this date.",
    "do_not_contact": "The buyer asked not to be contacted.",
}


@dataclass(frozen=True)
class FallbackAnalysis:
    label: Label
    rule_id: RuleId
    reason: str
    follow_up: date | None
    follow_up_basis: FollowUpReason
    follow_up_reason: str
    draft: str


def _draft(first_name: str, rule_id: RuleId, has_conversation: bool) -> str:
    if not has_conversation:
        return (
            f"Hi {first_name}, this is from the packaging equipment team. I wanted to check what "
            "you are looking to pack and the volumes you have in mind, so I can suggest the right "
            "machine. Is now a good time to talk?"
        )
    if rule_id == "C2":
        return (
            f"Hi {first_name}, I haven't heard back, so I'll pause my follow-ups for now. Whenever "
            "the packaging project is back on the table, just message me here."
        )
    return (
        f"Hi {first_name}, following up on our last conversation. Is there anything I can "
        "share or clarify to help you move forward?"
    )


def rules_only_analysis(*, buyer_name: str, facts: Facts, today: date) -> FallbackAnalysis:
    signals = Signals.unknown()
    label, rule_id = classify(signals, facts, today)
    follow_up, basis = next_follow_up(label, rule_id, signals, facts, today)
    first_name = buyer_name.split()[0] if buyer_name.split() else buyer_name
    description = RULE_DESCRIPTIONS[rule_id]
    return FallbackAnalysis(
        label=label,
        rule_id=rule_id,
        reason=f"Rule-based: {description}."[:160],
        follow_up=follow_up,
        follow_up_basis=basis,
        follow_up_reason=_FOLLOW_UP_REASONS[basis],
        draft=_draft(first_name, rule_id, facts.has_conversation),
    )
