from datetime import date, timedelta

from app.domain.rules import next_follow_up
from tests.domain.conftest import TODAY, facts, signals


def test_do_not_contact_has_no_date():
    assert next_follow_up("Cold", "C1", signals(do_not_contact=True), facts(), TODAY) == (
        None,
        "do_not_contact",
    )


def test_unanswered_buyer_question_is_due_on_the_day_it_was_asked():
    asked = date(2026, 10, 9)
    f = facts(last_sender="buyer", last_buyer_message_date=asked)
    result = next_follow_up("Warm", "W3", signals(awaiting_our_reply=True), f, TODAY)
    assert result == (asked, "awaiting_reply")


def test_awaiting_reply_is_ignored_when_the_rep_spoke_last():
    f = facts(last_sender="rep", last_contact_date=date(2026, 10, 11))
    _, reason = next_follow_up("Warm", "W1", signals(awaiting_our_reply=True), f, TODAY)
    assert reason == "cadence"


def test_future_commitment_is_honoured():
    s = signals(commitment_date=date(2026, 11, 15), commitment_made_on=date(2026, 10, 10))
    assert next_follow_up("Warm", "W2", s, facts(), TODAY) == (date(2026, 11, 15), "commitment")


def test_missed_commitment_stays_in_the_past_so_it_shows_overdue():
    s = signals(commitment_date=date(2026, 10, 9), commitment_made_on=date(2026, 10, 6))
    assert next_follow_up("Hot", "H1", s, facts(), TODAY) == (date(2026, 10, 9), "commitment")


def test_commitment_beyond_window_falls_back_to_cadence():
    s = signals(commitment_date=date(2027, 6, 1), commitment_made_on=date(2026, 10, 10))
    _, reason = next_follow_up("Warm", "W2", s, facts(), TODAY)
    assert reason == "cadence"


def test_commitment_before_the_message_it_was_made_in_is_rejected():
    s = signals(commitment_date=date(2026, 10, 1), commitment_made_on=date(2026, 10, 10))
    _, reason = next_follow_up("Warm", "W1", s, facts(), TODAY)
    assert reason == "cadence"


def test_commitment_without_a_known_message_date_is_rejected():
    s = signals(commitment_date=date(2026, 10, 20), commitment_made_on=None)
    _, reason = next_follow_up("Warm", "W1", s, facts(), TODAY)
    assert reason == "cadence"


def test_hot_cadence_is_one_day_after_last_contact():
    f = facts(last_contact_date=date(2026, 10, 10))
    assert next_follow_up("Hot", "H1", signals(), f, TODAY) == (date(2026, 10, 11), "cadence")


def test_warm_cadence_is_three_days_after_last_contact():
    f = facts(last_contact_date=date(2026, 10, 10))
    assert next_follow_up("Warm", "W1", signals(), f, TODAY) == (date(2026, 10, 13), "cadence")


def test_neglected_warm_lead_becomes_overdue_through_cadence():
    f = facts(last_contact_date=date(2026, 9, 20))
    date_, _ = next_follow_up("Warm", "W1", signals(), f, TODAY)
    assert date_ == date(2026, 9, 23)


def test_unresponsive_cold_lead_gets_a_gentle_close_in_fourteen_days():
    f = facts(last_contact_date=date(2026, 10, 10))
    assert next_follow_up("Cold", "C2", signals(), f, TODAY) == (date(2026, 10, 24), "cadence")


def test_lost_cold_lead_gets_a_check_in_after_ninety_days():
    f = facts(last_contact_date=date(2026, 10, 10))
    assert next_follow_up("Cold", "C1", signals(disqualified=True), f, TODAY) == (
        date(2027, 1, 8),
        "cadence",
    )


def test_cold_cadence_never_lands_in_the_past():
    # A stale Cold lead must not outrank today's Hot work by sitting at the top of Overdue.
    f = facts(has_conversation=False, last_contact_date=date(2026, 8, 1))
    date_, _ = next_follow_up("Cold", "C3", signals(), f, TODAY)
    assert date_ == TODAY + timedelta(days=14)


def test_never_contacted_lead_is_due_on_its_creation_day():
    f = facts(
        has_conversation=False,
        last_sender=None,
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        last_contact_date=None,
        created_date=TODAY,
    )
    assert next_follow_up("Warm", "W4", signals(), f, TODAY) == (TODAY, "first_touch")


def test_never_contacted_lead_left_untouched_becomes_overdue():
    created = date(2026, 10, 5)
    f = facts(
        has_conversation=False,
        last_sender=None,
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        last_contact_date=None,
        created_date=created,
    )
    assert next_follow_up("Warm", "W4", signals(), f, TODAY) == (created, "first_touch")


def test_stale_never_contacted_cold_lead_does_not_jump_to_the_top_of_overdue():
    # Regression from the live run: an import that sat untouched for 40 days took the first-touch
    # path (due on its creation day) and outranked every Hot lead in the queue.
    f = facts(
        has_conversation=False,
        last_sender=None,
        last_buyer_message_date=None,
        days_since_buyer_reply=None,
        last_contact_date=None,
        created_date=date(2026, 9, 2),
    )
    assert next_follow_up("Cold", "C3", signals(), f, TODAY) == (
        TODAY + timedelta(days=14),
        "cadence",
    )


def test_follow_up_is_never_before_the_lead_was_created():
    created = date(2026, 10, 11)
    s = signals(commitment_date=date(2026, 10, 10), commitment_made_on=date(2026, 10, 9))
    date_, _ = next_follow_up("Hot", "H1", s, facts(created_date=created), TODAY)
    assert date_ == created
