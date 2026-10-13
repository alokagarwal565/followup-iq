from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.domain.facts import MessageView, compute_facts
from tests.domain.conftest import TODAY

IST = ZoneInfo("Asia/Kolkata")
CREATED = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def msg(sender: str, sent: datetime, created: datetime | None = None) -> MessageView:
    return MessageView(sender_type=sender, sent_at=sent, created_at=created or sent)  # type: ignore[arg-type]


def test_lead_without_messages():
    f = compute_facts([], created_at=CREATED, last_contact_at=None, tz=IST, today=TODAY)
    assert f.has_conversation is False
    assert f.last_sender is None
    assert f.days_since_buyer_reply is None
    assert f.unanswered_rep_messages == 0
    assert f.last_contact_date is None
    assert f.created_date == date(2026, 9, 1)


def test_unanswered_rep_messages_counted_since_last_buyer_message():
    messages = [
        msg("rep", datetime(2026, 9, 1, 6, tzinfo=UTC)),
        msg("buyer", datetime(2026, 9, 2, 6, tzinfo=UTC)),
        msg("rep", datetime(2026, 9, 10, 6, tzinfo=UTC)),
        msg("rep", datetime(2026, 9, 20, 6, tzinfo=UTC)),
    ]
    f = compute_facts(messages, created_at=CREATED, last_contact_at=None, tz=IST, today=TODAY)
    assert f.last_sender == "rep"
    assert f.unanswered_rep_messages == 2
    assert f.last_buyer_message_date == date(2026, 9, 2)
    assert f.days_since_buyer_reply == 40


def test_dates_are_taken_in_the_business_timezone():
    # 20:00 UTC on 11 Oct is already 12 Oct in India.
    messages = [msg("buyer", datetime(2026, 10, 11, 20, 0, tzinfo=UTC))]
    f = compute_facts(messages, created_at=CREATED, last_contact_at=None, tz=IST, today=TODAY)
    assert f.last_buyer_message_date == date(2026, 10, 12)
    assert f.days_since_buyer_reply == 0


def test_last_contact_is_the_later_of_lead_field_and_newest_message():
    messages = [msg("buyer", datetime(2026, 10, 1, 6, tzinfo=UTC))]
    f = compute_facts(
        messages,
        created_at=CREATED,
        last_contact_at=datetime(2026, 10, 5, 6, tzinfo=UTC),
        tz=IST,
        today=TODAY,
    )
    assert f.last_contact_date == date(2026, 10, 5)


def test_messages_with_equal_sent_at_are_ordered_by_created_at():
    same = datetime(2026, 10, 10, 6, tzinfo=UTC)
    messages = [
        msg("rep", same, created=datetime(2026, 10, 10, 6, 0, 2, tzinfo=UTC)),
        msg("buyer", same, created=datetime(2026, 10, 10, 6, 0, 1, tzinfo=UTC)),
    ]
    f = compute_facts(messages, created_at=CREATED, last_contact_at=None, tz=IST, today=TODAY)
    assert f.last_sender == "rep"
    assert f.unanswered_rep_messages == 1
