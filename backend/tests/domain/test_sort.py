import random
from datetime import UTC, date, datetime

from app.domain.rules import QueueEntry, sort_queue
from tests.domain.conftest import TODAY


def entry(
    id_: str,
    follow_up: date | None,
    label: str | None = "Warm",
    awaiting: bool = False,
    last_contact: datetime | None = None,
) -> QueueEntry:
    return QueueEntry(
        id=id_,
        follow_up=follow_up,
        label=label,  # type: ignore[arg-type]
        awaiting_reply=awaiting,
        last_contact=last_contact,
    )


def ids(entries: list[QueueEntry]) -> list[str]:
    return [e.id for e in sort_queue(entries, TODAY)]


def test_buckets_are_overdue_then_today_then_upcoming_then_unscheduled():
    items = [
        entry("none", None),
        entry("up", date(2026, 10, 15)),
        entry("today", TODAY),
        entry("over", date(2026, 10, 1)),
    ]
    assert ids(items) == ["over", "today", "up", "none"]


def test_overdue_oldest_missed_date_first_then_label():
    items = [
        entry("cold-old", date(2026, 10, 1), "Cold"),
        entry("hot-recent", date(2026, 10, 10), "Hot"),
        entry("hot-old", date(2026, 10, 1), "Hot"),
    ]
    assert ids(items) == ["hot-old", "cold-old", "hot-recent"]


def test_today_puts_waiting_buyers_first_then_label_then_longest_silence():
    long_ago = datetime(2026, 10, 1, tzinfo=UTC)
    recently = datetime(2026, 10, 11, tzinfo=UTC)
    items = [
        entry("hot-recent", TODAY, "Hot", last_contact=recently),
        entry("warm-waiting", TODAY, "Warm", awaiting=True, last_contact=recently),
        entry("hot-long", TODAY, "Hot", last_contact=long_ago),
        entry("cold", TODAY, "Cold", last_contact=long_ago),
    ]
    assert ids(items) == ["warm-waiting", "hot-long", "hot-recent", "cold"]


def test_never_contacted_leads_count_as_longest_silence_today():
    items = [
        entry("contacted", TODAY, "Warm", last_contact=datetime(2026, 10, 1, tzinfo=UTC)),
        entry("never", TODAY, "Warm", last_contact=None),
    ]
    assert ids(items) == ["never", "contacted"]


def test_upcoming_nearest_first():
    items = [entry("later", date(2026, 10, 30)), entry("soon", date(2026, 10, 13))]
    assert ids(items) == ["soon", "later"]


def test_unanalyzed_leads_rank_after_labelled_ones_in_the_same_slot():
    items = [entry("pending", TODAY, None), entry("cold", TODAY, "Cold")]
    assert ids(items) == ["cold", "pending"]


def test_identical_keys_are_ordered_by_id():
    items = [entry("b", TODAY), entry("a", TODAY)]
    assert ids(items) == ["a", "b"]


def test_order_is_independent_of_input_order():
    items = [
        entry(f"lead-{i:02d}", date(2026, 10, 5 + i % 10), ["Hot", "Warm", "Cold"][i % 3])
        for i in range(30)
    ]
    expected = ids(items)
    shuffled = items[:]
    random.Random(7).shuffle(shuffled)
    assert ids(shuffled) == expected
