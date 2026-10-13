from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.ai.guards import (
    check_consistency,
    check_do_not_contact,
    check_invented_commitments,
    locate_commitment,
)
from app.ai.prompt import PromptMessage
from app.ai.schema import LeadAnalysisOut
from tests.ai.test_schema import VALID

IST = ZoneInfo("Asia/Kolkata")


def out(**overrides: object) -> LeadAnalysisOut:
    return LeadAnalysisOut.model_validate({**VALID, **overrides})


def test_invented_price_in_draft_is_flagged():
    errors = check_invented_commitments(
        "Hi Rahul, the price is ₹1.2 lakh per machine.", "Please share the quote."
    )
    assert errors and "₹1.2 lakh" in errors[0]


def test_price_already_in_conversation_is_allowed():
    convo = "BUYER: Your quote said ₹1.2 lakh, can you do better?"
    assert check_invented_commitments("Hi, on the ₹1.2 lakh quote, let me check.", convo) == []


def test_invented_discount_is_flagged():
    assert check_invented_commitments("We can offer 10% off this week.", "Send quote")
    assert check_invented_commitments("Happy to give a special discount.", "Send quote")


def test_discount_is_allowed_when_buyer_raised_it():
    convo = "BUYER: Any discount possible?"
    assert check_invented_commitments("On the discount you asked about, I'll check.", convo) == []


def test_invented_delivery_promise_is_flagged():
    assert check_invented_commitments("We can deliver by 20 October.", "Need machine soon")


def test_plain_follow_up_passes():
    assert check_invented_commitments("Hi Kavita, are we still on for Tuesday's demo?", "") == []


def test_label_disagreement_produces_a_rule_specific_repair_message():
    message = check_consistency(out(suggested_label="Hot"), rule_label="Warm", rule_id="W2")
    assert message is not None
    assert "Warm" in message and "W2" in message


def test_matching_label_passes_consistency():
    assert check_consistency(out(suggested_label="Hot"), rule_label="Hot", rule_id="H1") is None


def test_do_not_contact_with_a_draft_is_flagged():
    assert check_do_not_contact(out(do_not_contact=True, draft_message="Hi, checking in!"))


def test_contactable_lead_without_draft_is_flagged():
    assert check_do_not_contact(out(do_not_contact=False, draft_message=""))


def test_do_not_contact_without_draft_passes():
    assert check_do_not_contact(out(do_not_contact=True, draft_message="")) is None


def _messages() -> list[PromptMessage]:
    return [
        PromptMessage("buyer", datetime(2026, 10, 5, 6, tzinfo=UTC), "Need a quote for 2 fillers"),
        PromptMessage(
            "rep", datetime(2026, 10, 6, 20, tzinfo=UTC), "Sure, I will send the quote by Friday."
        ),
    ]


def test_commitment_quote_is_located_and_dated_in_business_timezone():
    # 20:00 UTC on the 6th is the 7th in India.
    found = locate_commitment("will send the quote by Friday", _messages(), IST)
    assert found == date(2026, 10, 7)


def test_commitment_quote_matching_ignores_case_and_spacing():
    assert locate_commitment("WILL send  the quote", _messages(), IST) == date(2026, 10, 7)


def test_commitment_quote_not_in_chat_is_rejected():
    assert locate_commitment("we will deliver free of cost", _messages(), IST) is None


def test_missing_commitment_quote_gives_no_date():
    assert locate_commitment(None, _messages(), IST) is None
