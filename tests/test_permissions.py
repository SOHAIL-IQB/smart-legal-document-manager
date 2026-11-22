"""Phase 2: every cell of the permission matrix in ADR 0001, plus sharing rules."""

import pytest

# role -> expected HTTP status. "outsider" is a signed-in user who isn't a member.
READ = {"owner": 200, "editor": 200, "viewer": 200, "outsider": 404}
EDIT = {"owner": 200, "editor": 200, "viewer": 403, "outsider": 404}
OWN = {"owner": 200, "editor": 403, "viewer": 403, "outsider": 404}

ACTIONS = {
    "get document": ("GET", "/api/documents/{id}", None, READ),
    "list versions": ("GET", "/api/documents/{id}/versions", None, READ),
    "compare": ("GET", "/api/documents/{id}/compare?v1=1&v2=1", None, READ),
    "list members": ("GET", "/api/documents/{id}/members", None, READ),
    "rename": ("PATCH", "/api/documents/{id}/title", {"title": "Renamed"}, EDIT),
    "add version": (
        "POST",
        "/api/documents/{id}/versions",
        {"content": "New wording."},
        {**EDIT, "owner": 201, "editor": 201},
    ),
    "delete version": ("DELETE", "/api/documents/{id}/versions/2", None, OWN),
    "add member": (
        "POST",
        "/api/documents/{id}/members",
        {"email": "erin@example.com", "role": "viewer"},
        {**OWN, "owner": 201},
    ),
    "change role": ("PATCH", "/api/documents/{id}/members/{viewer}", {"role": "editor"}, OWN),
    "delete document": ("DELETE", "/api/documents/{id}?confirm=true", None, OWN),
}


@pytest.fixture()
def team(client, signup, make_document):
    accounts = {
        "owner": signup("Olivia", "olivia@example.com"),
        "editor": signup("Ed", "ed@example.com"),
        "viewer": signup("Vera", "vera@example.com"),
        "outsider": signup("Otto", "otto@example.com"),
    }
    signup("Erin", "erin@example.com")
    owner = accounts["owner"]
    document_id = make_document(owner)
    client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "Second draft."},
        headers=owner.headers,
    )
    for role in ("editor", "viewer"):
        response = client.post(
            f"/api/documents/{document_id}/members",
            json={"email": accounts[role].email, "role": role},
            headers=owner.headers,
        )
        assert response.status_code == 201
    return document_id, accounts


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("role", ["owner", "editor", "viewer", "outsider"])
def test_permission_matrix(client, team, action, role):
    document_id, accounts = team
    method, path, body, expected = ACTIONS[action]
    url = path.format(id=document_id, viewer=accounts["viewer"].id)
    response = client.request(method, url, json=body, headers=accounts[role].headers)
    assert response.status_code == expected[role], response.text


def test_outsider_gets_same_404_as_missing_document(client, team):
    document_id, accounts = team
    outsider = accounts["outsider"].headers
    hidden = client.get(f"/api/documents/{document_id}", headers=outsider).json()
    missing = client.get("/api/documents/999999", headers=outsider).json()
    assert hidden["error"]["code"] == missing["error"]["code"] == "not_found"


def test_document_list_only_shows_my_documents_with_my_role(client, team, make_document):
    document_id, accounts = team
    make_document(accounts["outsider"], title="Otto's own")

    viewer_docs = client.get("/api/documents", headers=accounts["viewer"].headers).json()
    assert [(d["id"], d["my_role"]) for d in viewer_docs] == [(document_id, "viewer")]

    outsider_docs = client.get("/api/documents", headers=accounts["outsider"].headers).json()
    assert [d["title"] for d in outsider_docs] == ["Otto's own"]


# --- sharing rules ---------------------------------------------------------------


def test_member_list_shows_roles(client, team):
    document_id, accounts = team
    members = client.get(
        f"/api/documents/{document_id}/members", headers=accounts["viewer"].headers
    ).json()
    assert {m["email"]: m["role"] for m in members} == {
        "olivia@example.com": "owner",
        "ed@example.com": "editor",
        "vera@example.com": "viewer",
    }


def test_sharing_with_unknown_email_is_404(client, team):
    document_id, accounts = team
    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": "ghost@example.com"},
        headers=accounts["owner"].headers,
    )
    assert response.status_code == 404


def test_sharing_twice_is_conflict(client, team):
    document_id, accounts = team
    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": "ED@example.com", "role": "viewer"},
        headers=accounts["owner"].headers,
    )
    assert response.status_code == 409


def test_invalid_role_is_rejected(client, team):
    document_id, accounts = team
    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": "erin@example.com", "role": "admin"},
        headers=accounts["owner"].headers,
    )
    assert response.status_code == 422


def test_last_owner_cannot_be_demoted_or_leave(client, team):
    document_id, accounts = team
    owner = accounts["owner"]
    demote = client.patch(
        f"/api/documents/{document_id}/members/{owner.id}",
        json={"role": "editor"},
        headers=owner.headers,
    )
    leave = client.delete(f"/api/documents/{document_id}/members/{owner.id}", headers=owner.headers)
    assert demote.status_code == leave.status_code == 409


def test_owner_can_leave_once_another_owner_exists(client, team):
    document_id, accounts = team
    owner, editor = accounts["owner"], accounts["editor"]
    promote = client.patch(
        f"/api/documents/{document_id}/members/{editor.id}",
        json={"role": "owner"},
        headers=owner.headers,
    )
    assert promote.status_code == 200
    leave = client.delete(f"/api/documents/{document_id}/members/{owner.id}", headers=owner.headers)
    assert leave.status_code == 200
    assert client.get(f"/api/documents/{document_id}", headers=owner.headers).status_code == 404


def test_member_can_leave_but_not_remove_others(client, team):
    document_id, accounts = team
    viewer, editor = accounts["viewer"], accounts["editor"]
    remove_other = client.delete(
        f"/api/documents/{document_id}/members/{editor.id}", headers=viewer.headers
    )
    assert remove_other.status_code == 403
    leave = client.delete(
        f"/api/documents/{document_id}/members/{viewer.id}", headers=viewer.headers
    )
    assert leave.status_code == 200


def test_removed_member_loses_access(client, team):
    document_id, accounts = team
    owner, editor = accounts["owner"], accounts["editor"]
    client.delete(f"/api/documents/{document_id}/members/{editor.id}", headers=owner.headers)
    assert client.get(f"/api/documents/{document_id}", headers=editor.headers).status_code == 404


def test_changing_role_of_non_member_is_404(client, team):
    document_id, accounts = team
    response = client.patch(
        f"/api/documents/{document_id}/members/{accounts['outsider'].id}",
        json={"role": "editor"},
        headers=accounts["owner"].headers,
    )
    assert response.status_code == 404


def test_editor_versions_are_attributed_to_editor(client, team):
    document_id, accounts = team
    editor = accounts["editor"]
    client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": "Editor's wording."},
        headers=editor.headers,
    )
    versions = client.get(f"/api/documents/{document_id}/versions", headers=editor.headers).json()
    assert versions[-1]["edited_by"] == editor.id


def test_deleting_document_removes_memberships(client, team):
    document_id, accounts = team
    client.delete(f"/api/documents/{document_id}?confirm=true", headers=accounts["owner"].headers)
    assert client.get("/api/documents", headers=accounts["viewer"].headers).json() == []
