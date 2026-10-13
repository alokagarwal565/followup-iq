from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.domain.rules import business_today, days_overdue, due_state
from tests.domain.conftest import TODAY

IST = ZoneInfo("Asia/Kolkata")
NEW_YORK = ZoneInfo("America/New_York")


def test_missing_date_has_no_due_state():
    assert due_state(None, TODAY) == "none"


def test_yesterday_is_overdue():
    assert due_state(date(2026, 10, 11), TODAY) == "overdue"


def test_today_is_due_today():
    assert due_state(TODAY, TODAY) == "today"


def test_tomorrow_is_upcoming():
    assert due_state(date(2026, 10, 13), TODAY) == "upcoming"


def test_days_overdue_counts_calendar_days_and_is_zero_otherwise():
    assert days_overdue(date(2026, 10, 9), TODAY) == 3
    assert days_overdue(TODAY, TODAY) == 0
    assert days_overdue(None, TODAY) == 0


def test_business_today_just_before_ist_midnight():
    # 18:29:59 UTC is 23:59:59 in India, so it is still the 12th there.
    now = datetime(2026, 10, 12, 18, 29, 59, tzinfo=UTC)
    assert business_today(IST, now) == date(2026, 10, 12)


def test_business_today_at_ist_midnight_rolls_over_before_utc_does():
    now = datetime(2026, 10, 12, 18, 30, 0, tzinfo=UTC)
    assert business_today(IST, now) == date(2026, 10, 13)


def test_business_today_on_dst_change_day_in_new_york():
    # Clocks fall back on 1 Nov 2026: local midnight is 04:00 UTC before the change (EDT)
    # and 05:00 UTC after it (EST), so the day boundary moves by an hour.
    assert business_today(NEW_YORK, datetime(2026, 11, 1, 3, 59, tzinfo=UTC)) == date(2026, 10, 31)
    assert business_today(NEW_YORK, datetime(2026, 11, 1, 4, 0, tzinfo=UTC)) == date(2026, 11, 1)
    assert business_today(NEW_YORK, datetime(2026, 11, 2, 4, 59, tzinfo=UTC)) == date(2026, 11, 1)
    assert business_today(NEW_YORK, datetime(2026, 11, 2, 5, 0, tzinfo=UTC)) == date(2026, 11, 2)


def test_business_today_rejects_naive_datetimes():
    import pytest

    with pytest.raises(ValueError):
        business_today(IST, datetime(2026, 10, 12, 12, 0))
