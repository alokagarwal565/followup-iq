from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from app.db.queries import leads as lead_q
from tests.api.conftest import NOW, lead_payload

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def create(api, **overrides):
    response = await api.client.post("/api/v1/leads", json=lead_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_lead_persists_and_schedules_analysis(api):
    body = await create(api)
    lead = body["lead"]
    assert lead["name"] == "Rahul Mehta"
    assert lead["analysis_status"] == "pending"
    assert body["messages"] == []
    assert body["draft"]["status"] == "none"
    assert api.scheduler.calls == [(UUID(lead["id"]), False)]


async def test_create_lead_with_first_messages(api):
    body = await create(
        api,
        messages=[
            {"sender_type": "buyer", "body": "Need a quote", "sent_at": "2026-10-10T05:00:00Z"},
            {"sender_type": "rep", "body": "Sure", "sent_at": "2026-10-10T06:00:00Z"},
        ],
        client_request_id=str(uuid4()),
    )
    assert [m["body"] for m in body["messages"]] == ["Need a quote", "Sure"]
    assert body["lead"]["last_contact_at"].startswith("2026-10-10T06:00:00")


async def test_last_contact_date_is_stored_at_business_midday(api):
    body = await create(api, last_contact_date="2026-10-01")
    # 12:00 IST is 06:30 UTC, so the calendar day cannot shift in any timezone conversion.
    assert body["lead"]["last_contact_at"].startswith("2026-10-01T06:30:00")


async def test_future_last_contact_date_is_rejected(api):
    response = await api.client.post(
        "/api/v1/leads", json=lead_payload(last_contact_date="2026-10-20")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "last_contact_in_future"


async def test_duplicate_phone_in_another_format_is_rejected_with_the_existing_id(api):
    first = await create(api)
    response = await api.client.post(
        "/api/v1/leads", json=lead_payload(name="Someone Else", phone="+91-9000001001")
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "duplicate_phone"
    assert error["details"]["existing_lead_id"] == first["lead"]["id"]


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"company": ""}, "company"),
        ({"source": "Fax"}, "source"),
        ({"assigned_rep": "Nobody"}, "assigned_rep"),
        ({"phone": "call me maybe"}, "phone"),
        ({"budget": "10 lakh"}, "budget"),
    ],
)
async def test_invalid_lead_payloads_report_the_field(api, override, field):
    response = await api.client.post("/api/v1/leads", json=lead_payload(**override))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(field in loc["loc"] for loc in error["details"]["fields"])


async def test_replayed_create_request_returns_the_original_lead(api):
    request_id = str(uuid4())
    payload = lead_payload(
        messages=[{"sender_type": "buyer", "body": "Hello", "sent_at": "2026-10-11T05:00:00Z"}],
        client_request_id=request_id,
    )
    first = await api.client.post("/api/v1/leads", json=payload)
    second = await api.client.post("/api/v1/leads", json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["lead"]["id"] == second.json()["lead"]["id"]
    assert len(second.json()["messages"]) == 1
    assert len(api.scheduler.calls) == 1


async def test_unknown_and_malformed_ids(api):
    missing = await api.client.get(f"/api/v1/leads/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "lead_not_found"
    malformed = await api.client.get("/api/v1/leads/not-a-uuid")
    assert malformed.status_code == 422


async def test_queue_is_sorted_and_carries_due_state(api, pool):
    today = NOW.date()
    ids = {}
    for name, phone, due in [
        ("Upcoming", "+91 90000 02001", today + timedelta(days=2)),
        ("Overdue", "+91 90000 02002", today - timedelta(days=3)),
        ("Today", "+91 90000 02003", today),
        ("Unscheduled", "+91 90000 02004", None),
    ]:
        body = await create(api, name=name, phone=phone)
        ids[name] = body["lead"]["id"]
        async with pool.connection() as conn:
            await lead_q.update(
                conn,
                UUID(body["lead"]["id"]),
                next_follow_up_date=due,
                classification="Warm",
                analysis_status="ok",
            )
    response = await api.client.get("/api/v1/leads")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["name"] for i in items] == ["Overdue", "Today", "Upcoming", "Unscheduled"]
    assert [i["due_state"] for i in items] == ["overdue", "today", "upcoming", "none"]
    assert items[0]["days_overdue"] == 3
    assert response.json()["total"] == 4


async def test_queue_filters_by_rep_search_and_due_state(api, pool):
    a = await create(api)
    await create(api, name="Kavita Iyer", phone="+91 90000 02010", assigned_rep="Arjun Mehta")
    async with pool.connection() as conn:
        await lead_q.update(conn, UUID(a["lead"]["id"]), next_follow_up_date=date(2026, 10, 1))
    by_rep = (await api.client.get("/api/v1/leads", params={"rep": "Arjun Mehta"})).json()
    assert [i["name"] for i in by_rep["items"]] == ["Kavita Iyer"]
    by_q = (await api.client.get("/api/v1/leads", params={"q": "kavita"})).json()
    assert [i["name"] for i in by_q["items"]] == ["Kavita Iyer"]
    overdue = (await api.client.get("/api/v1/leads", params={"due_state": "overdue"})).json()
    assert [i["name"] for i in overdue["items"]] == ["Rahul Mehta"]


async def test_summary_counts_match_queue_definitions(api, pool):
    a = await create(api)
    b = await create(api, name="B", phone="+91 90000 02020")
    async with pool.connection() as conn:
        await lead_q.update(
            conn, UUID(a["lead"]["id"]), next_follow_up_date=date(2026, 10, 1), classification="Hot"
        )
        await lead_q.update(conn, UUID(b["lead"]["id"]), next_follow_up_date=NOW.date())
    summary = (await api.client.get("/api/v1/summary")).json()
    assert summary == {"overdue": 1, "today": 1, "hot": 1, "active": 2}


async def test_patch_updates_allowed_fields_and_guards_duplicates(api):
    a = await create(api)
    b = await create(api, name="B", phone="+91 90000 02030")
    lead_id = a["lead"]["id"]
    moved = await api.client.patch(
        f"/api/v1/leads/{lead_id}", json={"assigned_rep": "Sana Qureshi"}
    )
    assert moved.status_code == 200
    assert moved.json()["lead"]["assigned_rep"] == "Sana Qureshi"
    clash = await api.client.patch(f"/api/v1/leads/{lead_id}", json={"phone": b["lead"]["phone"]})
    assert clash.status_code == 409
    unknown = await api.client.patch(f"/api/v1/leads/{lead_id}", json={"classification": "Hot"})
    assert unknown.status_code == 422


async def test_stale_pending_analysis_is_reported_as_interrupted(api, pool):
    body = await create(api)
    async with pool.connection() as conn:
        await lead_q.update(
            conn,
            UUID(body["lead"]["id"]),
            analysis_status="pending",
            analysis_requested_at=NOW - timedelta(minutes=5),
        )
    lead = (await api.client.get(f"/api/v1/leads/{body['lead']['id']}")).json()["lead"]
    assert (lead["analysis_status"], lead["analysis_error"]) == ("failed", "interrupted")


async def test_meta_exposes_server_today_and_reference_lists(api):
    meta = (await api.client.get("/api/v1/meta")).json()
    assert meta["today"] == "2026-10-12"
    assert meta["business_tz"] == "Asia/Kolkata"
    assert "Priya Sharma" in meta["reps"] and "IndiaMART" in meta["sources"]
