from datetime import date

from app.domain.rules import classify
from tests.domain.conftest import TODAY, facts, signals


def test_disqualified_buyer_is_cold_c1():
    assert classify(signals(disqualified=True, intent="quote_requested"), facts(), TODAY) == (
        "Cold",
        "C1",
    )


def test_do_not_contact_is_cold_c1():
    assert classify(signals(do_not_contact=True), facts(), TODAY) == ("Cold", "C1")


def test_three_unanswered_follow_ups_and_long_silence_is_cold_c2():
    f = facts(
        last_sender="rep",
        unanswered_rep_messages=3,
        days_since_buyer_reply=25,
        last_buyer_message_date=date(2026, 9, 17),
    )
    assert classify(signals(intent="inquiry"), f, TODAY) == ("Cold", "C2")


def test_unanswered_follow_ups_from_a_buyer_who_never_replied_is_cold_c2():
    f = facts(
        last_sender="rep",
        unanswered_rep_messages=3,
        days_since_buyer_reply=None,
        last_buyer_message_date=None,
    )
    assert classify(signals(), f, TODAY) == ("Cold", "C2")


def test_unanswered_follow_ups_after_a_recent_reply_are_not_cold():
    f = facts(last_sender="rep", unanswered_rep_messages=3, days_since_buyer_reply=5)
    label, _ = classify(signals(intent="inquiry"), f, TODAY)
    assert label != "Cold"


def test_no_conversation_and_stale_contact_is_cold_c3():
    f = facts(
        has_conversation=False,
        last_sender=None,
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        last_contact_date=date(2026, 8, 28),
    )
    assert classify(signals(), f, TODAY) == ("Cold", "C3")


def test_never_contacted_lead_created_long_ago_is_cold_c3():
    f = facts(
        has_conversation=False,
        last_sender=None,
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        last_contact_date=None,
        created_date=date(2026, 8, 1),
    )
    assert classify(signals(), f, TODAY) == ("Cold", "C3")


def test_quote_request_with_short_timeline_and_recent_reply_is_hot_h1():
    s = signals(intent="quote_requested", timeline_days=10)
    assert classify(s, facts(days_since_buyer_reply=2), TODAY) == ("Hot", "H1")


def test_active_evaluation_counts_as_timeline_for_hot():
    s = signals(intent="demo_requested", evaluating=True)
    assert classify(s, facts(), TODAY) == ("Hot", "H1")


def test_strong_intent_with_stale_reply_is_not_hot():
    s = signals(intent="quote_requested", timeline_days=10)
    label, _ = classify(s, facts(days_since_buyer_reply=20), TODAY)
    assert label == "Warm"


def test_recent_contact_alone_is_not_hot():
    f = facts(days_since_buyer_reply=0, last_contact_date=TODAY)
    assert classify(signals(intent="none"), f, TODAY) == ("Warm", "W1")


def test_short_silence_alone_is_not_cold():
    f = facts(last_sender="rep", unanswered_rep_messages=1, days_since_buyer_reply=5)
    label, _ = classify(signals(intent="inquiry"), f, TODAY)
    assert label == "Warm"


def test_long_timeline_is_warm_w2_postponed():
    s = signals(intent="quote_requested", timeline_days=90)
    assert classify(s, facts(), TODAY) == ("Warm", "W2")


def test_evaluation_without_hot_criteria_is_warm_w3():
    s = signals(intent="inquiry", objection="spec", evaluating=True)
    assert classify(s, facts(), TODAY) == ("Warm", "W3")


def test_new_lead_without_conversation_is_warm_w4():
    f = facts(
        has_conversation=False,
        last_sender=None,
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        last_contact_date=None,
        created_date=TODAY,
    )
    assert classify(signals(), f, TODAY) == ("Warm", "W4")
