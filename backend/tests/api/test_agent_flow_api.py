"""Full request path with the real scheduler and analysis service, using the fake analyzer."""

from uuid import uuid4

import httpx
import pytest

from app.main import create_app
from tests.api.conftest import NOW, lead_payload, make_settings

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_logging_a_quote_request_updates_tag_date_and_draft(pool, clean_db):
    app = create_app(make_settings(gemini_fake=True), pool=pool, clock=lambda: NOW)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/api/v1/leads", json=lead_payload())
        lead_id = created.json()["lead"]["id"]
        # Background tasks complete before the in-process client returns, but the response body
        # is the pre-task snapshot, which is why the UI polls instead of trusting it.
        assert created.json()["lead"]["analysis_status"] == "pending"

        first = (await client.get(f"/api/v1/leads/{lead_id}")).json()
        assert first["lead"]["classification"] == "Warm"
        assert first["lead"]["due_state"] == "today"
        assert first["draft"]["status"] == "suggested"

        await client.post(
            f"/api/v1/leads/{lead_id}/messages",
            json={
                "client_request_id": str(uuid4()),
                "messages": [
                    {
                        "sender_type": "buyer",
                        "body": "Please send a quotation, we want to order this month.",
                    }
                ],
            },
        )
        updated = (await client.get(f"/api/v1/leads/{lead_id}")).json()
        assert updated["lead"]["classification"] == "Hot"
        assert updated["lead"]["analysis_status"] == "ok"
        assert updated["lead"]["rule_id"] == "H1"
        assert updated["draft"]["body"].startswith("Hi Rahul")
