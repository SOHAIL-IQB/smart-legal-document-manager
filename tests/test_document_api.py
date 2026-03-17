import logging


def create_user(client, *, name="Alice", email="alice@example.com") -> int:
    response = client.post("/users", json={"name": name, "email": email})
    assert response.status_code == 201
    return response.json()["id"]


def create_document(client, user_id: int, *, title="Service Agreement", content="Term is one year.") -> int:
    response = client.post(
        "/documents",
        json={"title": title, "content": content, "user_id": user_id},
    )
    assert response.status_code == 201
    return response.json()["document_id"]


def test_document_creation_creates_initial_version(client):
    user_id = create_user(client)

    response = client.post(
        "/documents",
        json={"title": "Master Services Agreement", "content": "Initial clause.", "user_id": user_id},
    )

    assert response.status_code == 201
    assert response.json() == {"document_id": 1, "version": 1}

    detail_response = client.get("/documents/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["version_count"] == 1
    assert detail_response.json()["latest_version"] == 1


def test_identical_content_does_not_create_new_version(client):
    user_id = create_user(client)
    document_id = create_document(client, user_id, content="This contract is valid for 1 year.")

    response = client.post(
        f"/documents/{document_id}/versions",
        json={"content": "This contract is valid for 1 year.", "user_id": user_id},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "No changes detected",
        "document_id": document_id,
        "version": None,
    }

    versions_response = client.get(f"/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1


def test_comparison_returns_unified_diff(client):
    user_id = create_user(client)
    document_id = create_document(client, user_id, content="This contract is valid for 1 year.")

    update_response = client.post(
        f"/documents/{document_id}/versions",
        json={"content": "This contract is valid for 2 years.", "user_id": user_id},
    )
    assert update_response.status_code == 201

    compare_response = client.get(f"/documents/{document_id}/compare?v1=1&v2=2")
    assert compare_response.status_code == 200

    payload = compare_response.json()
    assert payload["before"] == "This contract is valid for 1 year."
    assert payload["after"] == "This contract is valid for 2 years."
    assert payload["has_meaningful_changes"] is True
    assert any("-This contract is valid for 1 year." == line for line in payload["changes"])
    assert any("+This contract is valid for 2 years." == line for line in payload["changes"])


def test_title_update_does_not_create_version(client):
    user_id = create_user(client)
    document_id = create_document(client, user_id)

    patch_response = client.patch(f"/documents/{document_id}/title", json={"title": "Updated Title"})
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Updated Title"

    versions_response = client.get(f"/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1


def test_trivial_change_creates_version_without_notification(client, caplog):
    caplog.set_level(logging.INFO)
    user_id = create_user(client)
    document_id = create_document(client, user_id, content="Clause A\nClause B")

    response = client.post(
        f"/documents/{document_id}/versions",
        json={"content": "Clause A \nClause B", "user_id": user_id},
    )

    assert response.status_code == 201
    assert "updated by" not in caplog.text


def test_delete_version_and_document(client):
    user_id = create_user(client)
    document_id = create_document(client, user_id)

    second_version = client.post(
        f"/documents/{document_id}/versions",
        json={"content": "Term is two years.", "user_id": user_id},
    )
    assert second_version.status_code == 201

    delete_version_response = client.delete(f"/documents/{document_id}/versions/2")
    assert delete_version_response.status_code == 200

    versions_response = client.get(f"/documents/{document_id}/versions")
    assert len(versions_response.json()) == 1

    delete_without_confirm = client.delete(f"/documents/{document_id}")
    assert delete_without_confirm.status_code == 400

    delete_document_response = client.delete(f"/documents/{document_id}?confirm=true")
    assert delete_document_response.status_code == 200

    missing_response = client.get(f"/documents/{document_id}")
    assert missing_response.status_code == 404
