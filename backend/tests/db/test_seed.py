from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.cli.seed import rebase_demo, seed
from app.db.queries import leads as lead_q
from app.seed_data import SEED_LEADS, seed_lead_id
from tests.db.test_queries import new_lead

pytestmark = pytest.mark.asyncio(loop_scope="session")

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)


async def _count(conn, table: str) -> int:
    cur = await conn.execute(f"SELECT count(*) FROM {table}")
    row = await cur.fetchone()
    return int(row[0])


async def test_seed_inserts_leads_conversations_messages_and_empty_drafts(pool, clean_db):
    async with pool.connection() as conn:
        report = await seed(conn, now=NOW, tz=IST)
        assert report.leads_inserted == len(SEED_LEADS)
        assert await _count(conn, "leads") == len(SEED_LEADS)
        assert await _count(conn, "conversations") == sum(1 for s in SEED_LEADS if s.messages)
        assert await _count(conn, "messages") == sum(len(s.messages) for s in SEED_LEADS)
        assert await _count(conn, "drafts") == len(SEED_LEADS)


async def test_seed_is_idempotent(pool, clean_db):
    async with pool.connection() as conn:
        await seed(conn, now=NOW, tz=IST)
        second = await seed(conn, now=NOW + timedelta(days=1), tz=IST)
        assert second.leads_inserted == 0
        assert await _count(conn, "leads") == len(SEED_LEADS)
        assert await _count(conn, "messages") == sum(len(s.messages) for s in SEED_LEADS)


async def test_seeded_messages_use_relative_business_time(pool, clean_db):
    first = SEED_LEADS[0]
    async with pool.connection() as conn:
        await seed(conn, now=NOW, tz=IST)
        cur = await conn.execute(
            "SELECT min(m.sent_at) FROM messages m "
            "JOIN conversations c ON c.id = m.conversation_id WHERE c.lead_id = %s",
            (seed_lead_id(first.key),),
        )
        earliest = (await cur.fetchone())[0]
    oldest = first.messages[0]
    expected_day = NOW.astimezone(IST).date() - timedelta(days=oldest.days_ago)
    assert earliest.astimezone(IST).date() == expected_day
    assert earliest.astimezone(IST).strftime("%H:%M") == oldest.time


async def test_rebase_shifts_only_seeded_rows_by_whole_days(pool, clean_db):
    later = NOW + timedelta(days=5)
    async with pool.connection() as conn:
        await seed(conn, now=NOW, tz=IST)
        sample_id = seed_lead_id(SEED_LEADS[0].key)
        await lead_q.update(conn, sample_id, next_follow_up_date=NOW.date())
        before = await lead_q.get(conn, sample_id)
        user_id = await lead_q.insert(
            conn,
            new_lead(phone="+91 90000 09999", phone_digits="919000009999", last_contact_at=NOW),
        )
        shifted = await rebase_demo(conn, now=later, tz=IST)
        after = await lead_q.get(conn, sample_id)
        user_after = await lead_q.get(conn, user_id)
        second = await rebase_demo(conn, now=later, tz=IST)
    assert shifted == 5
    assert second == 0
    assert before is not None and after is not None and user_after is not None
    assert after.created_at - before.created_at == timedelta(days=5)
    assert after.next_follow_up_date == NOW.date() + timedelta(days=5)
    assert user_after.last_contact_at == NOW
