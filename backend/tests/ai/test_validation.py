import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.ai.prompt import PromptContext, PromptMessage
from app.ai.provider import Invalid, Valid
from app.ai.validation import make_validator
from app.domain.types import Facts
from tests.ai.test_schema import VALID

IST = ZoneInfo("Asia/Kolkata")
TODAY = date(2026, 10, 12)

MESSAGES = [
    PromptMessage(
        "buyer",
        datetime(2026, 10, 5, 6, tzinfo=UTC),
        "Need a quote for 2 fillers, ordering this month",
    ),
    PromptMessage("rep", datetime(2026, 10, 6, 6, tzinfo=UTC), "I will send the quote by Friday"),
    PromptMessage("buyer", datetime(2026, 10, 10, 6, tzinfo=UTC), "Any update?"),
]
FACTS = Facts(
    has_conversation=True,
    last_sender="buyer",
    last_buyer_message_date=date(2026, 10, 10),
    days_since_buyer_reply=2,
    unanswered_rep_messages=0,
    last_contact_date=date(2026, 10, 10),
    created_date=date(2026, 10, 1),
)


def validator():
    ctx = PromptContext(
        today=TODAY,
        tz=IST,
        rep_name="Priya Sharma",
        buyer_name="Rahul Mehta",
        company="Shree Snacks",
        source="IndiaMART",
        facts=FACTS,
        messages=MESSAGES,
    )
    return make_validator(ctx)


def answer(**overrides: object) -> str:
    return json.dumps({**VALID, "awaiting_our_reply": False, **overrides})


def test_valid_answer_is_classified_and_scheduled_by_the_rules():
    result = validator()(answer(), "STOP")
    assert isinstance(result, Valid)
    analysis = result.value
    assert (analysis.label, analysis.rule_id) == ("Hot", "H1")
    # The quote was found in the 6 Oct rep message, so the 16 Oct commitment is honoured.
    assert analysis.signals.commitment_made_on == date(2026, 10, 6)
    assert (analysis.follow_up, analysis.follow_up_basis) == (date(2026, 10, 16), "commitment")


def test_buyer_waiting_takes_priority_over_the_commitment():
    result = validator()(answer(awaiting_our_reply=True), "STOP")
    assert isinstance(result, Valid)
    assert (result.value.follow_up, result.value.follow_up_basis) == (
        date(2026, 10, 10),
        "awaiting_reply",
    )


def test_commitment_quote_not_in_the_chat_is_ignored_not_rejected():
    result = validator()(answer(commitment_quote="we promised free installation"), "STOP")
    assert isinstance(result, Valid)
    assert result.value.signals.commitment_date is None
    assert result.value.follow_up_basis == "cadence"


def test_label_that_disagrees_with_the_rules_is_sent_back_with_the_rule():
    result = validator()(answer(suggested_label="Cold"), "STOP")
    assert isinstance(result, Invalid)
    assert result.category == "malformed_output"
    assert "H1" in result.problem


def test_invented_price_in_the_draft_is_rejected():
    result = validator()(
        answer(draft_message="Hi Rahul, the price is ₹4.5 lakh per machine."), "STOP"
    )
    assert isinstance(result, Invalid)
    assert "4.5 lakh" in result.problem


def test_schema_violation_reports_field_paths():
    result = validator()(answer(reason="short"), "STOP")
    assert isinstance(result, Invalid)
    assert "reason" in result.problem


def test_non_json_is_malformed():
    result = validator()("Sure! Here is the analysis.", "STOP")
    assert isinstance(result, Invalid) and result.category == "malformed_output"


def test_empty_answer_after_a_safety_stop_is_a_safety_block():
    result = validator()("", "SAFETY")
    assert isinstance(result, Invalid) and result.category == "safety_blocked"
