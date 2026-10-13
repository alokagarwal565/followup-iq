from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def client() -> TestClient:
    settings = Settings(database_url="postgresql://u:p@localhost:1/none")
    # No pool: /health must answer without touching the database.
    return TestClient(create_app(settings, pool=None))


def test_health_responds_without_database():
    response = client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_error_envelope_with_request_id():
    response = client().get("/api/v1/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == response.headers["x-request-id"]


def test_incoming_request_id_is_echoed():
    response = client().get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_access_log_omits_query_strings(caplog):
    # Search terms are names and phone numbers; access logs must never record them.
    import logging

    logging.getLogger("followupiq").propagate = True
    with caplog.at_level(logging.INFO, logger="followupiq"):
        client().get("/health?q=Rahul+Mehta")
    records = [r for r in caplog.records if getattr(r, "fields", {}).get("event") == "http_request"]
    assert records, "expected one structured access line"
    fields = records[0].fields  # type: ignore[attr-defined]
    assert fields["path"] == "/health"
    assert fields["status"] == 200
    assert "Rahul" not in caplog.text and "Rahul" not in str(fields)


def test_oversized_body_is_rejected_before_routing():
    response = client().post(
        "/api/v1/anything", content=b"x" * (65 * 1024), headers={"content-type": "text/plain"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
