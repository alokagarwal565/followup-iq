from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.db.queries import drafts as draft_q
from app.db.queries import leads as lead_q
from tests.api.conftest import NOW, lead_payload

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def new_lead(api, **overrides) -> str:
    response = await api.client.post("/api/v1/leads", json=lead_payload(**overrides))
    assert response.status_code == 201, response.text
    api.scheduler.calls.clear()
    return response.json()["lead"]["id"]


async def log(api, lead_id, messages, request_id=None):
    return await api.client.post(
        f"/api/v1/leads/{lead_id}/messages",
        json={"client_request_id": request_id or str(uuid4()), "messages": messages},
    )


async def with_draft(pool, lead_id: str, body: str = "Hi Rahul, sharing the quote today.") -> int:
    async with pool.connection() as conn:
        await lead_q.update(
            conn,
            UUID(lead_id),
            classification="Warm",
            signals={"rule_id": "W1"},
            analysis_status="ok",
        )
        return await draft_q.update(conn, UUID(lead_id), body=body, status="suggested")


# --- Log chat -------------------------------------------------------------------------------


async def test_logging_messages_appends_updates_contact_and_schedules(api):
    lead_id = await new_lead(api)
    response = await log(
        api,
        lead_id,
        [
            {"sender_type": "buyer", "body": "Need 2 fillers", "sent_at": "2026-10-11T04:00:00Z"},
            {"sender_type": "rep", "body": "Sending quote", "sent_at": "2026-10-11T05:00:00Z"},
        ],
    )
    assert response.status_code == 201
    body = response.json()
    assert [m["body"] for m in body["messages"]] == ["Need 2 fillers", "Sending quote"]
    assert body["lead"]["analysis_status"] == "pending"
    assert body["lead"]["last_contact_at"].startswith("2026-10-11T05:00:00")
    assert api.scheduler.calls == [(UUID(lead_id), False)]


async def test_messages_without_a_time_keep_their_entered_order(api):
    lead_id = await new_lead(api)
    response = await log(
        api,
        lead_id,
        [{"sender_type": "buyer", "body": "one"}, {"sender_type": "rep", "body": "two"}],
    )
    assert [m["body"] for m in response.json()["messages"]] == ["one", "two"]


async def test_future_message_is_rejected(api):
    lead_id = await new_lead(api)
    future = (NOW + timedelta(hours=1)).isoformat()
    response = await log(api, lead_id, [{"sender_type": "buyer", "body": "x", "sent_at": future}])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "sent_at_in_future"


async def test_message_count_and_sender_are_validated(api):
    lead_id = await new_lead(api)
    too_many = [{"sender_type": "buyer", "body": f"m{i}"} for i in range(21)]
    assert (await log(api, lead_id, too_many)).status_code == 422
    assert (await log(api, lead_id, [{"sender_type": "bot", "body": "x"}])).status_code == 422
    assert (await log(api, lead_id, [{"sender_type": "buyer", "body": "   "}])).status_code == 422


async def test_replayed_log_chat_does_not_duplicate_or_reschedule(api):
    lead_id = await new_lead(api)
    request_id = str(uuid4())
    message = [{"sender_type": "buyer", "body": "Hello", "sent_at": "2026-10-11T04:00:00Z"}]
    await log(api, lead_id, message, request_id)
    replay = await log(api, lead_id, message, request_id)
    assert replay.status_code == 201
    assert len(replay.json()["messages"]) == 1
    assert len(api.scheduler.calls) == 1


async def test_logging_to_unknown_lead_is_404(api):
    response = await log(api, str(uuid4()), [{"sender_type": "buyer", "body": "x"}])
    assert response.status_code == 404


# --- Drafts ---------------------------------------------------------------------------------


async def test_saving_a_draft_marks_it_edited_and_checks_the_version(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    saved = await api.client.put(
        f"/api/v1/leads/{lead_id}/draft", json={"body": "Hi Rahul, edited.", "version": version}
    )
    assert saved.status_code == 200
    draft = saved.json()
    assert (draft["body"], draft["status"], draft["version"]) == (
        "Hi Rahul, edited.",
        "edited",
        version + 1,
    )
    stale = await api.client.put(
        f"/api/v1/leads/{lead_id}/draft", json={"body": "Other", "version": version}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"


async def test_accepting_a_suggestion_replaces_the_rep_edit(api, pool):
    lead_id = await new_lead(api)
    await with_draft(pool, lead_id)
    async with pool.connection() as conn:
        version = await draft_q.update(
            conn, UUID(lead_id), status="edited", suggested_body="Fresh AI suggestion"
        )
    accepted = await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/accept-suggestion", json={"version": version}
    )
    assert accepted.status_code == 200
    assert accepted.json()["body"] == "Fresh AI suggestion"
    assert accepted.json()["suggested_body"] is None


async def test_accepting_without_a_suggestion_is_rejected(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    response = await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/accept-suggestion", json={"version": version}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_suggestion"


async def test_mark_as_sent_records_the_message_and_reschedules_immediately(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    sent = await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/send",
        json={"body": "Hi Rahul, quote attached.", "version": version},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["messages"][-1]["body"] == "Hi Rahul, quote attached."
    assert body["messages"][-1]["origin"] == "draft_sent"
    assert body["draft"]["status"] == "sent"
    assert body["lead"]["last_contact_at"].startswith("2026-10-12T06:00:00")
    # Warm cadence (+3 days) applies at once so the lead leaves today's queue even if AI is down.
    assert body["lead"]["next_follow_up_date"] == "2026-10-15"
    assert body["lead"]["due_state"] == "upcoming"
    assert api.scheduler.calls == [(UUID(lead_id), False)]


async def test_repeated_send_is_idempotent(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    payload = {"body": "Hi Rahul, quote attached.", "version": version}
    await api.client.post(f"/api/v1/leads/{lead_id}/draft/send", json=payload)
    again = await api.client.post(f"/api/v1/leads/{lead_id}/draft/send", json=payload)
    assert again.status_code == 200
    assert sum(m["origin"] == "draft_sent" for m in again.json()["messages"]) == 1


async def test_sending_an_empty_draft_is_rejected(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    response = await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/send", json={"body": "  ", "version": version}
    )
    assert response.status_code == 422


async def test_do_not_contact_lead_cannot_be_sent_to(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    async with pool.connection() as conn:
        await lead_q.update(conn, UUID(lead_id), do_not_contact=True)
    response = await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/send", json={"body": "Hi", "version": version}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "do_not_contact"


async def test_undo_restores_everything_and_only_works_once(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    before = (await api.client.get(f"/api/v1/leads/{lead_id}")).json()
    await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/send", json={"body": "Sent text", "version": version}
    )
    undone = await api.client.post(f"/api/v1/leads/{lead_id}/draft/undo-send")
    assert undone.status_code == 200
    after = undone.json()
    assert after["messages"] == before["messages"]
    assert after["draft"]["body"] == before["draft"]["body"]
    assert after["draft"]["status"] == before["draft"]["status"]
    for key in ("last_contact_at", "next_follow_up_date", "analysis_status", "classification"):
        assert after["lead"][key] == before["lead"][key], key
    again = await api.client.post(f"/api/v1/leads/{lead_id}/draft/undo-send")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "nothing_to_undo"


async def test_undo_is_refused_once_a_newer_message_exists(api, pool):
    lead_id = await new_lead(api)
    version = await with_draft(pool, lead_id)
    await api.client.post(
        f"/api/v1/leads/{lead_id}/draft/send", json={"body": "Sent text", "version": version}
    )
    await log(api, lead_id, [{"sender_type": "buyer", "body": "Thanks!"}])
    response = await api.client.post(f"/api/v1/leads/{lead_id}/draft/undo-send")
    assert response.status_code == 409


# --- Analysis trigger -----------------------------------------------------------------------


async def test_manual_reanalysis_is_scheduled_with_force(api):
    lead_id = await new_lead(api)
    response = await api.client.post(f"/api/v1/leads/{lead_id}/analyze")
    assert response.status_code == 202
    assert response.json() == {"analysis_status": "pending"}
    assert api.scheduler.calls == [(UUID(lead_id), True)]
