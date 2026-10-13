"""Checks the model's answer against business rules before anything is saved.

Failures are fed back to the model in one bounded re-ask; output is never silently patched,
so prompt regressions surface as failures instead of hiding behind coercion.
"""

import re
import unicodedata
from datetime import date
from zoneinfo import ZoneInfo

from app.ai.prompt import PromptMessage
from app.ai.schema import LeadAnalysisOut
from app.domain.constants import RULE_DESCRIPTIONS
from app.domain.types import Label, RuleId

_MONEY = re.compile(
    r"(?:₹|rs\.?|inr|\$)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|lakhs|lac|crore|cr|k))?", re.IGNORECASE
)
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s?%")
_PROMISE_PHRASES = {
    "discount": re.compile(r"\bdiscount", re.IGNORECASE),
    "deliver": re.compile(r"\bdeliver(?:y|ed)?\s+(?:by|within|in)\b", re.IGNORECASE),
    "stock": re.compile(r"\bin\s+stock\b", re.IGNORECASE),
}


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def check_invented_commitments(draft: str, conversation: str) -> list[str]:
    """Flags prices, discounts, delivery or stock promises the conversation never mentioned."""
    convo = _squash(conversation)
    problems = []
    for pattern in (_MONEY, _PERCENT):
        for match in pattern.finditer(draft):
            if _squash(match.group()) not in convo:
                problems.append(
                    f'The draft mentions "{match.group().strip()}", which does not appear in the '
                    "conversation. Remove invented prices, percentages or amounts."
                )
    for topic, pattern in _PROMISE_PHRASES.items():
        if pattern.search(draft) and topic not in convo:
            problems.append(
                f'The draft promises or offers "{topic}" terms that the conversation never '
                "mentioned. Do not invent discounts, delivery dates or stock availability."
            )
    return problems


def check_consistency(out: LeadAnalysisOut, *, rule_label: Label, rule_id: RuleId) -> str | None:
    if out.suggested_label == rule_label:
        return None
    return (
        f"Business rules classify this lead as {rule_label} (rule {rule_id}: "
        f"{RULE_DESCRIPTIONS[rule_id]}). Set suggested_label to {rule_label} and rewrite the "
        f"reason, follow_up_reason and draft_message so they are consistent with {rule_label}."
    )


def check_do_not_contact(out: LeadAnalysisOut) -> str | None:
    has_draft = bool(out.draft_message.strip())
    if out.do_not_contact and has_draft:
        return "The buyer asked not to be contacted, so draft_message must be an empty string."
    if not out.do_not_contact and not has_draft:
        return "draft_message is empty; write the next WhatsApp follow-up message."
    return None


def locate_commitment(
    quote: str | None, messages: list[PromptMessage], tz: ZoneInfo
) -> date | None:
    """Business-TZ date of the message the commitment quote came from, or None if it isn't there.

    Requiring a verbatim quote stops the model from inventing commitments, and the message's own
    date is what relative phrases like "Friday" were resolved against.
    """
    if not quote or not quote.strip():
        return None
    needle = _squash(quote)
    for message in sorted(messages, key=lambda m: m.sent_at, reverse=True):
        if needle in _squash(message.body):
            return message.sent_at.astimezone(tz).date()
    return None
