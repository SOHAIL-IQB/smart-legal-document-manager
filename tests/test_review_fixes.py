"""Regression tests for review findings R1-R3 (LOG.md entry 009). Written before the fixes."""

import pytest
from sqlalchemy import event, select

from app.core.config import get_settings
from app.db.models import DocumentMember, DocumentVersion
from app.db.session import SessionLocal, engine

CSRF = {"X-Requested-With": "XMLHttpRequest"}


def chunks(total_bytes: int, prefix: bytes = b"", suffix: bytes = b"", size: int = 1024):
    """A body sent with Transfer-Encoding: chunked (no Content-Length)."""

    def generate():
        yield prefix
        sent = 0
        while sent < total_bytes:
            yield b"a" * size
            sent += size
        yield suffix

    return generate()


# --- R1: request bodies are capped while they stream in ---------------------------------
# These use the real limits (fixed when the app is built): ~9-10 MB generated in memory.

MULTIPART_HEAD = (
    b'--XyZ\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n'
    b"Content-Type: text/plain\r\n\r\n"
)


def test_chunked_json_over_the_limit_is_refused_without_auth(client):
    over = get_settings().max_json_bytes + 1024
    response = client.post(
        "/api/auth/login",
        content=chunks(over, b'{"email":"a@x.com","password":"', b'"}', size=64 * 1024),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_declared_json_over_the_limit_is_refused(client, alice):
    body = b'{"title":"Big","content":"' + b"x" * (get_settings().max_json_bytes + 1) + b'"}'
    response = client.post(
        "/api/documents",
        content=body,
        headers={**alice.headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_largest_allowed_content_still_fits(client, alice):
    # 2,000,000 characters of 4-byte UTF-8 is the worst case the content rules allow.
    response = client.post(
        "/api/documents",
        json={"title": "Huge but allowed", "content": "😀" * 2_000_000},
        headers=alice.headers,
    )
    assert response.status_code == 201


def test_chunked_upload_over_the_limit_is_refused_before_auth(client):
    over = get_settings().max_upload_bytes + 128 * 1024
    response = client.post(
        "/api/documents/upload",
        content=chunks(over, MULTIPART_HEAD, b"\r\n--XyZ--\r\n", size=64 * 1024),
        headers={"Content-Type": "multipart/form-data; boundary=XyZ"},
    )
    assert response.status_code == 413  # refused while streaming, not 401 after reading it all


def test_upload_route_allows_more_than_the_json_limit(client, alice):
    # 9.5 MB file: over the 9 MB JSON limit but within the 10 MB upload limit. Mostly blank
    # lines (collapsed when the text is normalized), so the extracted text stays short.
    data = b"Clause one.\n" + b"\n" * (19 * 1024 * 1024 // 2) + b"Clause two."
    assert get_settings().max_json_bytes < len(data) < get_settings().max_upload_bytes
    response = client.post(
        "/api/documents/upload",
        files={"file": ("big.txt", data, "text/plain")},
        headers=alice.headers,
    )
    assert response.status_code == 201


# --- R2: deleting a document doesn't load its versions --------------------------------------


def test_deleting_a_document_does_not_load_version_content(client, alice, make_document):
    document_id = make_document(alice, content="v1 " + "x" * 10_000)
    for i in range(2, 6):
        client.post(
            f"/api/documents/{document_id}/versions",
            json={"content": f"v{i} " + "x" * 10_000},
            headers=alice.headers,
        )
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()))

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = client.delete(
            f"/api/documents/{document_id}?confirm=true", headers=alice.headers
        )
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert response.status_code == 200
    assert not [s for s in statements if s.startswith("SELECT") and "document_versions" in s]
    assert not [s for s in statements if s.startswith("DELETE FROM document_versions")]
    with SessionLocal() as db:  # the database cascade removed the children
        assert (
            db.scalars(
                select(DocumentVersion).where(DocumentVersion.document_id == document_id)
            ).all()
            == []
        )
        assert (
            db.scalars(
                select(DocumentMember).where(DocumentMember.document_id == document_id)
            ).all()
            == []
        )


# --- R3: every cookie-authenticated write needs the CSRF header -----------------------------


@pytest.fixture()
def cookie_session(client, make_document, signup):
    """`client` holds Carol's session cookie; returns (client, document id, Carol)."""
    client.post(
        "/api/auth/register",
        json={"name": "Carol", "email": "carol@example.com", "password": "correct horse battery"},
    )
    created = client.post(
        "/api/documents", json={"title": "T", "content": "v1"}, headers=CSRF
    ).json()["document_id"]
    client.post(f"/api/documents/{created}/versions", json={"content": "v2"}, headers=CSRF)
    return client, created


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/documents/{id}/versions", {"content": "v3"}),
        ("PATCH", "/api/documents/{id}/title", {"title": "Renamed"}),
        ("DELETE", "/api/documents/{id}/versions/2", None),
        ("DELETE", "/api/documents/{id}?confirm=true", None),
        ("POST", "/api/documents/{id}/versions/1/restore", None),
    ],
)
def test_cookie_writes_without_csrf_header_are_refused(cookie_session, method, path, body):
    client, document_id = cookie_session
    url = path.format(id=document_id)

    refused = client.request(method, url, json=body)
    assert refused.status_code == 403
    assert "X-Requested-With" in refused.json()["error"]["message"]

    allowed = client.request(method, url, json=body, headers=CSRF)
    assert allowed.status_code in (200, 201)


def test_413_carries_cors_headers_so_the_browser_can_read_it(client):
    body = b'{"email":"a@x.com","password":"' + b"x" * (get_settings().max_json_bytes + 1) + b'"}'
    response = client.post(
        "/api/auth/login",
        content=body,
        headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
    )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_declared_oversized_body_is_refused_without_reading_it():
    import asyncio

    from app.core.limits import BodySizeLimitMiddleware

    app_called = False

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        raise AssertionError("the body was read")

    sent = []

    async def send(message):
        sent.append(message)

    too_big = str(get_settings().max_json_bytes + 1).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/documents",
        "headers": [(b"content-length", too_big)],
    }
    asyncio.run(BodySizeLimitMiddleware(app)(scope, receive, send))

    assert app_called is False
    assert sent[0]["status"] == 413
    assert b'"payload_too_large"' in sent[1]["body"]
