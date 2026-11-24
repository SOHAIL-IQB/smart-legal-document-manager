"""Phase 1: consistent error shape (B7), input validation (B5), config safety (B13)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app

# --- B5: blank input -------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "content", "bad_field"),
    [(" ", "Real clause.", "title"), ("NDA", "   \n\t ", "content"), ("", "x", "title")],
)
def test_blank_title_or_content_is_rejected(client, alice, title, content, bad_field):
    response = client.post(
        "/api/documents", json={"title": title, "content": content}, headers=alice.headers
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert any(detail["field"] == bad_field for detail in body["details"])


def test_blank_version_content_is_rejected(client, alice, make_document):
    document_id = make_document(alice)
    response = client.post(
        f"/api/documents/{document_id}/versions", json={"content": "  "}, headers=alice.headers
    )
    assert response.status_code == 422


def test_title_is_trimmed(client, alice, make_document):
    document_id = make_document(alice)
    response = client.patch(
        f"/api/documents/{document_id}/title", json={"title": "  Lease  "}, headers=alice.headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Lease"


def test_content_whitespace_is_preserved_exactly(client, alice, make_document):
    content = "  Indented clause.\n\nSecond clause.  \n"
    document_id = make_document(alice, content=content)
    version = client.get(f"/api/documents/{document_id}/versions/1", headers=alice.headers).json()
    assert version["content"] == content


def test_compare_rejects_non_positive_versions(client, alice, make_document):
    document_id = make_document(alice)
    response = client.get(f"/api/documents/{document_id}/compare?v1=0&v2=1", headers=alice.headers)
    assert response.status_code == 422


# --- B7: consistent error shape -------------------------------------------


def test_missing_document_returns_not_found_shape(client, alice):
    response = client.get("/api/documents/999", headers=alice.headers)
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Document 999 was not found.",
            "request_id": response.headers["x-request-id"],
        }
    }


def test_missing_version_returns_not_found(client, alice, make_document):
    document_id = make_document(alice)
    response = client.get(f"/api/documents/{document_id}/compare?v1=1&v2=7", headers=alice.headers)
    assert response.status_code == 404
    assert "Version 7" in response.json()["error"]["message"]


def test_unknown_route_uses_error_shape(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_delete_without_confirm_is_bad_request(client, alice, make_document):
    document_id = make_document(alice)
    response = client.delete(f"/api/documents/{document_id}", headers=alice.headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_unexpected_error_returns_generic_500(monkeypatch, alice):
    def boom(*_args, **_kwargs):
        raise RuntimeError("database exploded with secret details")

    monkeypatch.setattr("app.services.documents.search_documents", boom)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/documents", headers=alice.headers
    )
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "request_id": response.headers["x-request-id"],
        }
    }  # internal details are not leaked


# --- B13: CORS -------------------------------------------------------------


def test_wildcard_cors_origin_is_rejected():
    with pytest.raises(ValidationError, match="cannot contain"):
        Settings(cors_origins=["*"])


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Requested-With, Content-Type",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/api/documents",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_health(client):
    # Since Phase 7 the health check is a readiness check that also reports the database.
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}


# Review finding M2: PostgreSQL can't store NUL in text, so these answered 500 there (and SQLite
# stored them). They are refused at the boundary with a 422 on both databases.
NUL = "before\u0000after"


@pytest.mark.parametrize(
    "case",
    [
        "document title",
        "document content",
        "new title",
        "version content",
        "change note",
        "account name",
        "search query",
        "upload title",
        "upload change note",
    ],
)
def test_nul_characters_are_refused_with_a_422(client, alice, make_document, case):
    document_id = make_document(alice)
    docs = f"/api/documents/{document_id}"
    txt = {"file": ("a.txt", b"Plain text.", "text/plain")}
    requests = {
        "document title": ("POST", "/api/documents", {"json": {"title": NUL, "content": "x"}}),
        "document content": ("POST", "/api/documents", {"json": {"title": "T", "content": NUL}}),
        "new title": ("PATCH", f"{docs}/title", {"json": {"title": NUL}}),
        "version content": ("POST", f"{docs}/versions", {"json": {"content": NUL}}),
        "change note": (
            "POST",
            f"{docs}/versions",
            {"json": {"content": "new", "change_note": NUL}},
        ),
        "search query": ("GET", "/api/documents", {"params": {"q": NUL}}),
        "upload title": ("POST", "/api/documents/upload", {"files": txt, "data": {"title": NUL}}),
        "upload change note": (
            "POST",
            f"{docs}/versions/upload",
            {"files": txt, "data": {"change_note": NUL}},
        ),
    }
    if case == "account name":
        body = {"name": NUL, "email": "nul@example.com", "password": "correct horse battery"}
        response = client.post("/api/auth/register", json=body)
    else:
        method, url, kwargs = requests[case]
        response = client.request(method, url, headers=alice.headers, **kwargs)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
