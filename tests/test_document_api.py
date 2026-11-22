"""The original six behaviour tests, ported to authenticated requests.

Each test keeps its original assertions; only the way the actor is identified changed
(a bearer token instead of a `user_id` in the body).
"""

import logging


def test_document_creation_creates_initial_version(client, alice):
    response = client.post(
        "/api/documents",
        json={"title": "Master Services Agreement", "content": "Initial clause."},
        headers=alice.headers,
    )

    assert response.status_code == 201
    assert response.json() == {"document_id": 1, "version": 1}

    detail_response = client.get("/api/documents/1", headers=alice.headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["version_count"] == 1
    assert detail_response.json()["latest_version"] == 1
    assert detail_response.json()["my_role"] == "owner"


def test_identical_content_does_not_create_new_version(client, alice, make_document):
    document_id = make_document(alice, content="This contract is valid for 1 year.")

    response = client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "This contract is valid for 1 year."},
        headers=alice.headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "No changes detected",
        "document_id": document_id,
        "version": None,
    }

    versions_response = client.get(f"/api/documents/{document_id}/versions", headers=alice.headers)
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1


def test_comparison_returns_unified_diff(client, alice, make_document):
    document_id = make_document(alice, content="This contract is valid for 1 year.")

    update_response = client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "This contract is valid for 2 years."},
        headers=alice.headers,
    )
    assert update_response.status_code == 201

    compare_response = client.get(
        f"/api/documents/{document_id}/compare?v1=1&v2=2", headers=alice.headers
    )
    assert compare_response.status_code == 200

    payload = compare_response.json()
    assert payload["before"] == "This contract is valid for 1 year."
    assert payload["after"] == "This contract is valid for 2 years."
    assert payload["has_meaningful_changes"] is True
    assert any(line == "-This contract is valid for 1 year." for line in payload["changes"])
    assert any(line == "+This contract is valid for 2 years." for line in payload["changes"])


def test_title_update_does_not_create_version(client, alice, make_document):
    document_id = make_document(alice)

    patch_response = client.patch(
        f"/api/documents/{document_id}/title",
        json={"title": "Updated Title"},
        headers=alice.headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Updated Title"

    versions_response = client.get(f"/api/documents/{document_id}/versions", headers=alice.headers)
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1


def test_trivial_change_creates_version_without_notification(client, alice, make_document, caplog):
    caplog.set_level(logging.INFO)
    document_id = make_document(alice, content="Clause A\nClause B")

    response = client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "Clause A \nClause B"},
        headers=alice.headers,
    )

    assert response.status_code == 201
    assert "updated by" not in caplog.text


def test_meaningful_change_sends_notification(client, alice, make_document, caplog):
    """Counterpart to the trivial-change test: proves the notification path actually fires."""
    caplog.set_level(logging.INFO)
    document_id = make_document(alice, content="Clause A")

    response = client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "Clause A, amended"},
        headers=alice.headers,
    )

    assert response.status_code == 201
    assert f"Document {document_id} updated by Alice" in caplog.text


def test_delete_version_and_document(client, alice, make_document):
    document_id = make_document(alice)

    second_version = client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "Term is two years."},
        headers=alice.headers,
    )
    assert second_version.status_code == 201

    delete_version_response = client.delete(
        f"/api/documents/{document_id}/versions/2", headers=alice.headers
    )
    assert delete_version_response.status_code == 200

    versions_response = client.get(f"/api/documents/{document_id}/versions", headers=alice.headers)
    assert len(versions_response.json()) == 1

    delete_without_confirm = client.delete(f"/api/documents/{document_id}", headers=alice.headers)
    assert delete_without_confirm.status_code == 400

    delete_document_response = client.delete(
        f"/api/documents/{document_id}?confirm=true", headers=alice.headers
    )
    assert delete_document_response.status_code == 200

    missing_response = client.get(f"/api/documents/{document_id}", headers=alice.headers)
    assert missing_response.status_code == 404


def test_version_records_the_authenticated_editor(client, alice, make_document):
    document_id = make_document(alice)
    client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "Term: 2 years."},
        headers=alice.headers,
    )
    versions = client.get(f"/api/documents/{document_id}/versions", headers=alice.headers).json()
    assert {v["edited_by"] for v in versions} == {alice.id}
