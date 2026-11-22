"""Phase 1: consistent error shape (B7), input validation (B5), config safety (B13)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


def make_user(client, email="alice@example.com") -> int:
    response = client.post("/api/users", json={"name": "Alice", "email": email})
    assert response.status_code == 201
    return response.json()["id"]


def make_document(client, user_id, content="Clause 1.") -> int:
    response = client.post(
        "/api/documents", json={"title": "NDA", "content": content, "user_id": user_id}
    )
    assert response.status_code == 201
    return response.json()["document_id"]


# --- B5: blank input -------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "content", "bad_field"),
    [(" ", "Real clause.", "title"), ("NDA", "   \n\t ", "content"), ("", "x", "title")],
)
def test_blank_title_or_content_is_rejected(client, title, content, bad_field):
    user_id = make_user(client)
    response = client.post(
        "/api/documents", json={"title": title, "content": content, "user_id": user_id}
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert any(detail["field"] == bad_field for detail in body["details"])


def test_blank_version_content_is_rejected(client):
    user_id = make_user(client)
    document_id = make_document(client, user_id)
    response = client.post(
        f"/api/documents/{document_id}/versions", json={"content": "  ", "user_id": user_id}
    )
    assert response.status_code == 422


def test_title_is_trimmed(client):
    user_id = make_user(client)
    document_id = make_document(client, user_id)
    response = client.patch(f"/api/documents/{document_id}/title", json={"title": "  Lease  "})
    assert response.status_code == 200
    assert response.json()["title"] == "Lease"


def test_content_whitespace_is_preserved_exactly(client):
    user_id = make_user(client)
    content = "  Indented clause.\n\nSecond clause.  \n"
    document_id = make_document(client, user_id, content=content)
    versions = client.get(f"/api/documents/{document_id}/versions").json()
    assert versions[0]["content"] == content


def test_compare_rejects_non_positive_versions(client):
    user_id = make_user(client)
    document_id = make_document(client, user_id)
    response = client.get(f"/api/documents/{document_id}/compare?v1=0&v2=1")
    assert response.status_code == 422


# --- B7: consistent error shape -------------------------------------------


def test_missing_document_returns_not_found_shape(client):
    response = client.get("/api/documents/999")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Document 999 was not found."}
    }


def test_missing_user_on_create_returns_not_found(client):
    response = client.post("/api/documents", json={"title": "T", "content": "c", "user_id": 42})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_missing_version_returns_not_found(client):
    user_id = make_user(client)
    document_id = make_document(client, user_id)
    response = client.get(f"/api/documents/{document_id}/compare?v1=1&v2=7")
    assert response.status_code == 404
    assert "Version 7" in response.json()["error"]["message"]


def test_unknown_route_uses_error_shape(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_delete_without_confirm_is_bad_request(client):
    user_id = make_user(client)
    document_id = make_document(client, user_id)
    response = client.delete(f"/api/documents/{document_id}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_duplicate_email_is_conflict_case_insensitive(client):
    make_user(client, email="alice@example.com")
    response = client.post("/api/users", json={"name": "A2", "email": "ALICE@example.com"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_unexpected_error_returns_generic_500(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("database exploded with secret details")

    monkeypatch.setattr("app.services.users.list_users", boom)
    response = TestClient(app, raise_server_exceptions=False).get("/api/users")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "An unexpected error occurred."}
    }  # internal details are not leaked


# --- B13: CORS -------------------------------------------------------------


def test_wildcard_cors_origin_is_rejected():
    with pytest.raises(ValidationError, match="cannot contain"):
        Settings(cors_origins=["*"])


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/documents",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
