from datetime import date

import pytest

from app.domain.types import Facts, Signals

TODAY = date(2026, 10, 12)


def signals(**overrides: object) -> Signals:
    base: dict[str, object] = {
        "intent": "none",
        "timeline_days": None,
        "evaluating": False,
        "objection": "none",
        "disqualified": False,
        "do_not_contact": False,
        "awaiting_our_reply": False,
        "commitment_date": None,
        "commitment_made_on": None,
    }
    base.update(overrides)
    return Signals(**base)  # type: ignore[arg-type]


def facts(**overrides: object) -> Facts:
    base: dict[str, object] = {
        "has_conversation": True,
        "last_sender": "buyer",
        "last_buyer_message_date": date(2026, 10, 10),
        "days_since_buyer_reply": 2,
        "unanswered_rep_messages": 0,
        "last_contact_date": date(2026, 10, 10),
        "created_date": date(2026, 9, 1),
    }
    base.update(overrides)
    return Facts(**base)  # type: ignore[arg-type]


@pytest.fixture
def today() -> date:
    return TODAY
