"""Deterministic business rules: tag, follow-up date, due state and queue order.

Gemini only supplies `Signals`; every decision that must be explainable and stable lives here.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain import constants as c
from app.domain.types import DueState, Facts, FollowUpReason, Label, RuleId, Signals

_LABEL_RANK: dict[Label | None, int] = {"Hot": 0, "Warm": 1, "Cold": 2, None: 3}
_BUCKET_RANK: dict[DueState, int] = {"overdue": 0, "today": 1, "upcoming": 2, "none": 3}


def business_today(tz: ZoneInfo, now: datetime | None = None) -> date:
    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None:
        raise ValueError("business_today needs a timezone-aware datetime")
    return now.astimezone(tz).date()


def classify(signals: Signals, facts: Facts, today: date) -> tuple[Label, RuleId]:
    """First matching rule wins; the order encodes precedence (disqualification beats intent)."""
    if signals.disqualified or signals.do_not_contact:
        return "Cold", "C1"

    silent_long_enough = (
        facts.days_since_buyer_reply is None
        or facts.days_since_buyer_reply >= c.COLD_MIN_SILENCE_DAYS
    )
    if (
        facts.has_conversation
        and facts.unanswered_rep_messages >= c.COLD_MIN_UNANSWERED
        and silent_long_enough
    ):
        return "Cold", "C2"

    if not facts.has_conversation and _is_stale_without_conversation(facts, today):
        return "Cold", "C3"

    has_near_timeline = (
        signals.timeline_days is not None and signals.timeline_days <= c.HOT_MAX_TIMELINE_DAYS
    )
    replied_recently = (
        facts.days_since_buyer_reply is not None
        and facts.days_since_buyer_reply <= c.HOT_MAX_DAYS_SINCE_REPLY
    )
    if (
        signals.intent in c.STRONG_INTENTS
        and (has_near_timeline or signals.evaluating)
        and replied_recently
    ):
        return "Hot", "H1"

    if not facts.has_conversation:
        return "Warm", "W4"
    if signals.timeline_days is not None and signals.timeline_days > c.HOT_MAX_TIMELINE_DAYS:
        return "Warm", "W2"
    if signals.evaluating or signals.objection != "none":
        return "Warm", "W3"
    return "Warm", "W1"


def _is_stale_without_conversation(facts: Facts, today: date) -> bool:
    # Excel imports carry a last-contact date older than the row itself, so prefer it when present.
    reference = facts.last_contact_date or facts.created_date
    return (today - reference).days >= c.STALE_CONTACT_DAYS


def next_follow_up(
    label: Label, rule_id: RuleId, signals: Signals, facts: Facts, today: date
) -> tuple[date | None, FollowUpReason]:
    """Response urgency is decided separately from purchase intent, in priority order."""
    if signals.do_not_contact:
        return None, "do_not_contact"

    # A buyer waiting on us is due the day they asked, whatever the tag: a Warm lead can be today's
    # most urgent item. The fact check guards against the model claiming this after a rep reply.
    if (
        signals.awaiting_our_reply
        and facts.last_sender == "buyer"
        and facts.last_buyer_message_date is not None
    ):
        return _not_before_creation(facts.last_buyer_message_date, facts), "awaiting_reply"

    commitment = _valid_commitment(signals)
    if commitment is not None:
        # A missed commitment intentionally stays in the past so it surfaces as overdue.
        return _not_before_creation(commitment, facts), "commitment"

    # First touch is due the day a live lead arrives; a stale Cold import falls through to the
    # Cold cadence below so it cannot sit at the top of Overdue ahead of real work.
    if facts.last_contact_date is None and not facts.has_conversation and label != "Cold":
        return facts.created_date, "first_touch"

    base = facts.last_contact_date or facts.created_date
    if label == "Cold":
        gap = timedelta(days=c.COLD_LOST_DAYS if rule_id == "C1" else c.COLD_UNRESPONSIVE_DAYS)
        # A lapsed Cold cadence restarts from today instead of landing in the past: stale cold leads
        # would otherwise flood Overdue and outrank live Hot work. Cold leads still go overdue
        # through missed promises or unanswered questions, which are handled above.
        due = base + gap
        return (due if due >= today else today + gap), "cadence"
    return _not_before_creation(base + timedelta(days=c.CADENCE_DAYS[label]), facts), "cadence"


def _valid_commitment(signals: Signals) -> date | None:
    made_on, promised = signals.commitment_made_on, signals.commitment_date
    if made_on is None or promised is None:
        return None
    if made_on <= promised <= made_on + timedelta(days=c.COMMITMENT_WINDOW_DAYS):
        return promised
    return None


def _not_before_creation(value: date, facts: Facts) -> date:
    return max(value, facts.created_date)


def due_state(follow_up: date | None, today: date) -> DueState:
    if follow_up is None:
        return "none"
    if follow_up < today:
        return "overdue"
    if follow_up == today:
        return "today"
    return "upcoming"


def days_overdue(follow_up: date | None, today: date) -> int:
    if follow_up is None or follow_up >= today:
        return 0
    return (today - follow_up).days


@dataclass(frozen=True)
class QueueEntry:
    id: str
    follow_up: date | None
    label: Label | None
    awaiting_reply: bool
    last_contact: datetime | None


def queue_sort_key(entry: QueueEntry, today: date) -> tuple[object, ...]:
    state = due_state(entry.follow_up, today)
    bucket = _BUCKET_RANK[state]
    label = _LABEL_RANK[entry.label]
    if state == "overdue":
        return (bucket, entry.follow_up, label, entry.id)
    if state == "today":
        # Never-contacted leads have waited longest, so they sort before any real timestamp.
        silence = entry.last_contact.timestamp() if entry.last_contact else float("-inf")
        return (bucket, 0 if entry.awaiting_reply else 1, label, silence, entry.id)
    if state == "upcoming":
        return (bucket, entry.follow_up, label, entry.id)
    return (bucket, label, entry.id)


def sort_queue(entries: Iterable[QueueEntry], today: date) -> list[QueueEntry]:
    return sorted(entries, key=lambda e: queue_sort_key(e, today))
