from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.queries import drafts as draft_q
from app.db.queries import leads as lead_q
from app.db.queries import messages as message_q
from app.db.queries.leads import NewLeadRow

pytestmark = pytest.mark.asyncio(loop_scope="session")

NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)


def new_lead(**overrides: object) -> NewLeadRow:
    base: dict[str, object] = {
        "name": "Rahul Mehta",
        "company": "Shree Snacks Pvt Ltd",
        "phone": "+91 90000 01001",
        "phone_digits": "919000001001",
        "source": "IndiaMART",
        "assigned_rep": "Priya Sharma",
        "last_contact_at": None,
    }
    base.update(overrides)
    return NewLeadRow(**base)  # type: ignore[arg-type]


async def test_inserted_lead_has_never_analyzed_defaults(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        lead = await lead_q.get(conn, lead_id)
    assert lead is not None
    assert lead.analysis_status == "never"
    assert lead.evidence == []
    assert lead.classification is None


async def test_unknown_lead_returns_none(pool, clean_db):
    async with pool.connection() as conn:
        assert await lead_q.get(conn, uuid4()) is None


async def test_find_by_phone_digits(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        assert await lead_q.find_by_phone_digits(conn, "919000001001") == lead_id
        assert await lead_q.find_by_phone_digits(conn, "910000000000") is None


async def test_list_filters_by_rep_classification_and_search(pool, clean_db):
    async with pool.connection() as conn:
        a = await lead_q.insert(conn, new_lead())
        b = await lead_q.insert(
            conn,
            new_lead(
                name="Kavita Iyer",
                company="Masala Magic Foods",
                phone="+91 90000 01002",
                phone_digits="919000001002",
                assigned_rep="Arjun Mehta",
            ),
        )
        await lead_q.update(conn, b, classification="Hot")
        assert {r.id for r in await lead_q.list_leads(conn)} == {a, b}
        assert [r.id for r in await lead_q.list_leads(conn, rep="Arjun Mehta")] == [b]
        assert [r.id for r in await lead_q.list_leads(conn, classification="Hot")] == [b]
        assert [r.id for r in await lead_q.list_leads(conn, q="masala")] == [b]
        assert [r.id for r in await lead_q.list_leads(conn, q="1001")] == [a]


async def test_search_treats_wildcards_literally(pool, clean_db):
    async with pool.connection() as conn:
        await lead_q.insert(conn, new_lead())
        assert await lead_q.list_leads(conn, q="%") == []
        assert await lead_q.list_leads(conn, q="_") == []
        assert await lead_q.list_leads(conn, q="' OR 1=1 --") == []


async def test_update_rejects_columns_outside_the_allow_list(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        with pytest.raises(ValueError):
            await lead_q.update(conn, lead_id, id=uuid4())


async def test_update_stores_jsonb_values(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        await lead_q.update(conn, lead_id, evidence=["a", "b"], signals={"rule_id": "H1"})
        lead = await lead_q.get(conn, lead_id)
    assert lead is not None
    assert lead.evidence == ["a", "b"]
    assert lead.rule_id == "H1"


async def test_conversation_is_created_once_and_reused(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        first = await message_q.ensure_conversation(conn, lead_id)
        second = await message_q.ensure_conversation(conn, lead_id)
    assert first == second


async def test_messages_are_returned_in_chronological_then_entry_order(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        conv = await message_q.ensure_conversation(conn, lead_id)
        await message_q.insert(conn, conv, "rep", "second", NOW, origin="logged")
        await message_q.insert(conn, conv, "buyer", "first", NOW - timedelta(hours=1))
        await message_q.insert(conn, conv, "buyer", "third", NOW, origin="logged")
        bodies = [m.body for m in await message_q.for_lead(conn, lead_id)]
    assert bodies == ["first", "second", "third"]


async def test_same_timestamp_messages_in_one_transaction_keep_entry_order(pool, clean_db):
    # Regression: created_at defaulted to now(), which is constant within a transaction, so the
    # tie-break fell through to random UUIDs and order flickered between runs.
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        conv = await message_q.ensure_conversation(conn, lead_id)
        async with conn.transaction():
            for i in range(5):
                await message_q.insert(conn, conv, "buyer", f"m{i}", NOW)
        bodies = [m.body for m in await message_q.for_lead(conn, lead_id)]
    assert bodies == [f"m{i}" for i in range(5)]


async def test_request_id_lookup(pool, clean_db):
    request_id = uuid4()
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        conv = await message_q.ensure_conversation(conn, lead_id)
        assert await message_q.lead_for_request(conn, request_id) is None
        await message_q.insert(conn, conv, "buyer", "hi", NOW, request_id=request_id)
        assert await message_q.lead_for_request(conn, request_id) == lead_id


async def test_draft_updates_always_bump_the_version(pool, clean_db):
    async with pool.connection() as conn:
        lead_id = await lead_q.insert(conn, new_lead())
        await draft_q.create(conn, lead_id)
        draft = await draft_q.get(conn, lead_id)
        assert draft is not None and (draft.status, draft.version) == ("none", 1)
        await draft_q.update(conn, lead_id, body="Hi Rahul", status="suggested")
        draft = await draft_q.get(conn, lead_id, for_update=True)
    assert draft is not None
    assert (draft.body, draft.status, draft.version) == ("Hi Rahul", "suggested", 2)
