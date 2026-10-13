import pytest

from tests.api.conftest import lead_payload, make_api

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_sql_like_search_is_inert(api):
    await api.client.post("/api/v1/leads", json=lead_payload())
    response = await api.client.get("/api/v1/leads", params={"q": "%' OR 1=1 --"})
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_markup_in_messages_is_stored_and_returned_verbatim(api):
    created = await api.client.post("/api/v1/leads", json=lead_payload())
    lead_id = created.json()["lead"]["id"]
    payload = "<script>alert(1)</script>"
    response = await api.client.post(
        f"/api/v1/leads/{lead_id}/messages",
        json={
            "client_request_id": "6b0f7c1e-3c42-4bb4-9a31-1f1a3c2d4e5f",
            "messages": [{"sender_type": "buyer", "body": payload}],
        },
    )
    assert response.json()["messages"][0]["body"] == payload


async def test_control_characters_are_stripped_from_text(api):
    created = await api.client.post("/api/v1/leads", json=lead_payload(name="Rahul\x00 Mehta\x07"))
    assert created.json()["lead"]["name"] == "Rahul Mehta"


async def test_write_rate_limit_returns_429(pool, clean_db):
    _, client = await make_api(pool, rate_limit_writes_per_min=2)
    async with client:
        statuses = []
        for i in range(3):
            response = await client.post(
                "/api/v1/leads", json=lead_payload(phone=f"+91 90000 0300{i}")
            )
            statuses.append(response.status_code)
        assert statuses == [201, 201, 429]
        assert response.json()["error"]["code"] == "rate_limited"
        # Reads are not throttled by the write budget.
        assert (await client.get("/api/v1/leads")).status_code == 200


async def test_rate_limit_cannot_be_dodged_with_a_forged_forwarded_header(pool, clean_db):
    # The proxy appends the real client IP last; a client-supplied first entry must not count.
    _, client = await make_api(pool, rate_limit_writes_per_min=2)
    async with client:
        statuses = []
        for i in range(3):
            response = await client.post(
                "/api/v1/leads",
                json=lead_payload(phone=f"+91 90000 0310{i}"),
                headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"},
            )
            statuses.append(response.status_code)
        assert statuses == [201, 201, 429]


async def test_cors_allows_only_configured_origins(api):
    allowed = await api.client.options(
        "/api/v1/leads",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    denied = await api.client.options(
        "/api/v1/leads",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers


async def test_readiness_reports_db_and_ai_without_secrets(api):
    response = await api.client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "ai": "unconfigured"}
