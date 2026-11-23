"""Every "safe to retry" row in ADR 0002 (docs/adr/0002-api-contract.md), checked by replaying the
request after it succeeded. The two endpoints documented as unsafe are checked too."""

from tests.files import make_pdf


def twice(client, method, url, account, **kwargs):
    first = client.request(method, url, headers=account.headers, **kwargs)
    second = client.request(method, url, headers=account.headers, **kwargs)
    return first, second


def test_register_retry_is_a_409(client):
    body = {"name": "R", "email": "r@example.com", "password": "correct horse battery"}
    first = client.post("/api/auth/register", json=body)
    second = client.post("/api/auth/register", json=body)
    assert (first.status_code, second.status_code) == (201, 409)


def test_rename_retry_changes_nothing(client, alice, make_document):
    document_id = make_document(alice)
    url = f"/api/documents/{document_id}/title"
    first, second = twice(client, "PATCH", url, alice, json={"title": "Lease"})
    assert first.status_code == second.status_code == 200
    activity = client.get(f"/api/documents/{document_id}/activity", headers=alice.headers).json()
    assert [e["action"] for e in activity["items"]].count("document.renamed") == 1


def test_delete_document_retry_is_a_404(client, alice, make_document):
    document_id = make_document(alice)
    first, second = twice(client, "DELETE", f"/api/documents/{document_id}?confirm=true", alice)
    assert (first.status_code, second.status_code) == (200, 404)


def test_version_retry_creates_nothing(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    url = f"/api/documents/{document_id}/versions"
    first, second = twice(client, "POST", url, alice, json={"content": "v2"})
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["message"] == "No changes detected"


def test_version_upload_retry_creates_nothing(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    url = f"/api/documents/{document_id}/versions/upload"
    files = {"file": ("v2.txt", b"v2", "text/plain")}
    first = client.post(url, files=files, headers=alice.headers)
    second = client.post(
        url, files={"file": ("v2.txt", b"v2", "text/plain")}, headers=alice.headers
    )
    assert (first.status_code, second.status_code) == (201, 200)


def test_restore_retry_creates_nothing(client, alice, make_document):
    document_id = make_document(alice, content="A")
    client.post(
        f"/api/documents/{document_id}/versions", json={"content": "B"}, headers=alice.headers
    )
    url = f"/api/documents/{document_id}/versions/1/restore"
    first, second = twice(client, "POST", url, alice)
    assert (first.status_code, second.status_code) == (201, 200)


def test_delete_version_retry_is_a_410(client, alice, make_document):
    document_id = make_document(alice, content="A")
    client.post(
        f"/api/documents/{document_id}/versions", json={"content": "B"}, headers=alice.headers
    )
    first, second = twice(client, "DELETE", f"/api/documents/{document_id}/versions/2", alice)
    assert (first.status_code, second.status_code) == (200, 410)


def test_share_retry_is_a_409_and_role_change_retry_is_harmless(
    client, alice, signup, make_document
):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice)
    url = f"/api/documents/{document_id}/members"
    first, second = twice(client, "POST", url, alice, json={"email": bob.email, "role": "viewer"})
    assert (first.status_code, second.status_code) == (201, 409)
    role_url = f"{url}/{bob.id}"
    first, second = twice(client, "PATCH", role_url, alice, json={"role": "editor"})
    assert first.status_code == second.status_code == 200
    first, second = twice(client, "DELETE", role_url, alice)
    assert (first.status_code, second.status_code) == (200, 404)


def test_notification_read_retries_are_harmless(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice)
    client.post(
        f"/api/documents/{document_id}/members",
        json={"email": bob.email, "role": "viewer"},
        headers=alice.headers,
    )
    item = client.get("/api/notifications", headers=bob.headers).json()["items"][0]["id"]
    first, second = twice(client, "POST", f"/api/notifications/{item}/read", bob)
    assert first.json()["read_at"] == second.json()["read_at"]
    first, second = twice(client, "POST", "/api/notifications/read-all", bob)
    assert second.json() == {"updated": 0}


def test_documented_unsafe_endpoints_really_duplicate(client, alice):
    body = {"title": "NDA", "content": "Terms."}
    client.post("/api/documents", json=body, headers=alice.headers)
    client.post("/api/documents", json=body, headers=alice.headers)
    files = {"file": ("nda.pdf", make_pdf("Terms."), "application/pdf")}
    client.post("/api/documents/upload", files=files, headers=alice.headers)
    files = {"file": ("nda.pdf", make_pdf("Terms."), "application/pdf")}
    client.post("/api/documents/upload", files=files, headers=alice.headers)
    assert client.get("/api/documents", headers=alice.headers).json()["total"] == 4
