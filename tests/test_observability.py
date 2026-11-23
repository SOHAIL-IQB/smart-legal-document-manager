"""Phase 7 T7: request IDs and structured JSON logs.

On-call questions these signals answer (docs/specs/phase-7-hardening.md, Slice C):
2. Why did this specific user's request fail? -> the request ID they see, found in the logs.
3. Which endpoints are slow or failing? -> one access line per request with route and duration.
4. Are people locked out or uploads refused, and why? -> named domain events with reason codes.
"""

import json
import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from app.main import app
from tests.conftest import PASSWORD


@pytest.fixture()
def logs(caplog):
    caplog.set_level(logging.INFO, logger="sldm")
    return caplog


def events(caplog, name):
    return [r for r in caplog.records if getattr(r, "event", None) == name]


def fields(record):
    return {"event": record.event, **record.fields}


# --- request IDs -----------------------------------------------------------------------------


def test_every_response_gets_a_request_id(client):
    for response in (client.get("/api/health"), client.get("/api/nope")):
        uuid.UUID(response.headers["x-request-id"])  # raises if not a UUID


def test_a_valid_incoming_request_id_is_kept(client):
    incoming = str(uuid.uuid4())
    response = client.get("/api/health", headers={"X-Request-ID": incoming})
    assert response.headers["x-request-id"] == incoming


@pytest.mark.parametrize("incoming", ["abc", "x" * 200, "'; DROP TABLE users; --"])
def test_an_invalid_incoming_request_id_is_replaced(client, incoming):
    response = client.get("/api/health", headers={"X-Request-ID": incoming})
    assert response.headers["x-request-id"] != incoming
    uuid.UUID(response.headers["x-request-id"])


def test_error_bodies_carry_the_request_id(client, alice):
    response = client.get("/api/documents/999", headers=alice.headers)
    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_validation_errors_carry_the_request_id(client, alice):
    response = client.post("/api/documents", json={}, headers=alice.headers)
    assert response.status_code == 422
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_unhandled_error_is_logged_and_answered_with_the_same_request_id(monkeypatch, alice, logs):
    def boom(*_args, **_kwargs):
        raise RuntimeError("database exploded with secret details")

    monkeypatch.setattr("app.services.documents.search_documents", boom)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/documents", headers=alice.headers
    )
    request_id = response.headers["x-request-id"]

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "request_id": request_id,
        }
    }
    [record] = events(logs, "unhandled_error")
    assert record.fields["request_id"] == request_id
    assert record.exc_info is not None  # the stack trace goes to the log, never to the client


# --- access log --------------------------------------------------------------------------------


def test_one_access_line_per_request_with_route_template(client, alice, make_document, logs):
    document_id = make_document(alice)
    logs.clear()
    response = client.get(f"/api/documents/{document_id}", headers=alice.headers)

    [line] = events(logs, "http_request")
    assert fields(line) == {
        "event": "http_request",
        "request_id": response.headers["x-request-id"],
        "method": "GET",
        "route": "/api/documents/{document_id}",  # template, so metrics/queries group by route
        "status": 200,
        "duration_ms": line.fields["duration_ms"],
        "user_id": alice.id,
    }
    assert isinstance(line.fields["duration_ms"], float)


def test_unmatched_paths_are_not_logged_verbatim(client, logs):
    client.get("/api/does/not/exist/12345")
    [line] = events(logs, "http_request")
    assert line.fields["route"] == "unmatched"
    assert line.fields["status"] == 404
    assert "user_id" not in line.fields


# --- domain events -----------------------------------------------------------------------------


def test_failed_login_is_logged_without_the_email_or_password(client, signup, logs):
    signup("Bob", "bob@example.com")
    client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong-pass-1"})
    [record] = events(logs, "login_failed")
    assert record.fields["reason"] == "invalid_credentials"
    assert "bob@example.com" not in json.dumps(record.fields)


def test_rate_limited_login_is_logged(client, logs):
    for _ in range(11):
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope-nope"})
    assert len(events(logs, "login_rate_limited")) == 1


def test_rejected_upload_is_logged_with_a_reason_code(client, alice, logs):
    client.post(
        "/api/documents/upload",
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        headers=alice.headers,
    )
    [record] = events(logs, "upload_rejected")
    assert record.fields["reason"] == "unsupported_media_type"


def test_no_secret_ever_reaches_the_logs(client, logs):
    register = client.post(
        "/api/auth/register",
        json={"name": "Eve", "email": "eve@example.com", "password": PASSWORD},
    )
    token = register.json()["access_token"]
    client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    client.post("/api/auth/login", json={"email": "eve@example.com", "password": PASSWORD})

    formatter = JsonFormatter()
    output = "\n".join(formatter.format(r) for r in logs.records)
    for secret in (PASSWORD, token, "eve@example.com"):
        assert secret not in output


# --- JSON format ---------------------------------------------------------------------------------


def test_json_formatter_writes_one_parseable_object_per_line():
    record = logging.LogRecord("sldm", logging.WARNING, __file__, 1, "login_failed", None, None)
    record.event = "login_failed"
    record.fields = {"request_id": "abc", "reason": "invalid_credentials"}
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert "\n" not in line
    assert parsed["level"] == "warning"
    assert parsed["event"] == "login_failed"
    assert parsed["reason"] == "invalid_credentials"
    assert parsed["ts"].endswith("Z")
