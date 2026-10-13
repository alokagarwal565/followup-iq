from dataclasses import dataclass
from datetime import date
from typing import Literal

Label = Literal["Hot", "Warm", "Cold"]
RuleId = Literal["C1", "C2", "C3", "H1", "W1", "W2", "W3", "W4"]
Intent = Literal[
    "none", "inquiry", "quote_requested", "demo_requested", "negotiating", "ready_to_order"
]
Objection = Literal["none", "price", "competitor", "timing", "spec"]
DueState = Literal["overdue", "today", "upcoming", "none"]
FollowUpReason = Literal["do_not_contact", "awaiting_reply", "commitment", "cadence", "first_touch"]
Sender = Literal["rep", "buyer"]


@dataclass(frozen=True)
class Signals:
    """What the conversation says, as read by Gemini. Never trusted for dates or counts."""

    intent: Intent
    timeline_days: int | None
    evaluating: bool
    objection: Objection
    disqualified: bool
    do_not_contact: bool
    awaiting_our_reply: bool
    commitment_date: date | None
    # Business-TZ date of the message containing the commitment; anchors the plausibility window.
    commitment_made_on: date | None

    @classmethod
    def unknown(cls) -> "Signals":
        """Neutral signals for the rules-only fallback, where nothing can be read from the chat."""
        return cls(
            intent="none",
            timeline_days=None,
            evaluating=False,
            objection="none",
            disqualified=False,
            do_not_contact=False,
            awaiting_our_reply=False,
            commitment_date=None,
            commitment_made_on=None,
        )


@dataclass(frozen=True)
class Facts:
    """What the database says. Computed in code, never asked of the model."""

    has_conversation: bool
    last_sender: Sender | None
    last_buyer_message_date: date | None
    days_since_buyer_reply: int | None
    unanswered_rep_messages: int
    last_contact_date: date | None
    created_date: date
