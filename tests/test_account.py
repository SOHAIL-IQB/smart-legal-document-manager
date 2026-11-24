"""Phase 7 T15: export your data, and delete (anonymize) your account.

Spec: docs/specs/phase-7-hardening.md, addendum T15.
"""

import json
import logging

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.models import (
    ActivityEvent,
    Document,
    DocumentMember,
    DocumentVersion,
    Notification,
    User,
)
from app.db.session import SessionLocal
from tests.conftest import PASSWORD

EXPORT = "/api/auth/me/export"
ME = "/api/auth/me"


def share(client, owner, document_id, member, role="editor"):
    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": member.email, "role": role},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text


def add_version(client, account, document_id, content):
    response = client.post(
        f"/api/documents/{document_id}/versions", json={"content": content}, headers=account.headers
    )
    assert response.status_code == 201, response.text


def delete_account(client, account, password=PASSWORD):
    return client.request("DELETE", ME, json={"password": password}, headers=account.headers)


def count(model, *where):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where))


# --- export ----------------------------------------------------------------------------------


def test_export_contains_everything_listed_for_the_signed_in_user(
    client, alice, signup, make_document
):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice, title="Lease", content="Rent: 100.")
    share(client, alice, document_id, bob, role="editor")
    add_version(client, bob, document_id, "Rent: 120.")

    response = client.get(EXPORT, headers=bob.headers)

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert ".json" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    data = json.loads(response.content)
    assert set(data) == {
        "format_version",
        "exported_at",
        "profile",
        "memberships",
        "versions_authored",
        "activity",
        "notifications",
    }
    assert data["profile"]["email"] == "bob@example.com"
    assert data["profile"]["name"] == "Bob"
    assert [(m["document_id"], m["title"], m["role"]) for m in data["memberships"]] == [
        (document_id, "Lease", "editor")
    ]
    [version] = data["versions_authored"]
    assert (version["document_id"], version["version_number"], version["content"]) == (
        document_id,
        2,
        "Rent: 120.",
    )
    assert [event["action"] for event in data["activity"]] == ["version.created"]
    assert [n["kind"] for n in data["notifications"]] == ["document_shared"]


def test_export_leaves_out_documents_you_can_no_longer_access(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice, title="Secret deal")
    share(client, alice, document_id, bob)
    add_version(client, bob, document_id, "Bob's draft.")
    removed = client.delete(f"/api/documents/{document_id}/members/{bob.id}", headers=alice.headers)
    assert removed.status_code == 200

    data = client.get(EXPORT, headers=bob.headers).json()

    assert data["memberships"] == []
    assert data["versions_authored"] == []
    assert data["activity"] == []
    # His own inbox is his, including the notice that he was removed.
    assert {n["kind"] for n in data["notifications"]} == {
        "document_shared",
        "removed_from_document",
    }


def test_export_never_includes_another_users_inbox_or_documents(
    client, alice, signup, make_document
):
    bob = signup("Bob", "bob@example.com")
    make_document(alice, title="Alice only")
    other = make_document(bob, title="Bob's")
    share(client, bob, other, alice)  # Alice gets a notification; Bob must not see it

    data = client.get(EXPORT, headers=bob.headers).json()

    assert [m["title"] for m in data["memberships"]] == ["Bob's"]
    assert data["notifications"] == []


def test_export_needs_sign_in(client):
    assert client.get(EXPORT).status_code == 401


# --- deletion: refusals --------------------------------------------------------------------


def test_wrong_password_is_refused_and_changes_nothing(client, alice):
    response = delete_account(client, alice, password="not my password")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get(ME, headers=alice.headers).status_code == 200


def test_password_is_required(client, alice):
    response = client.request("DELETE", ME, json={}, headers=alice.headers)
    assert response.status_code == 422


def test_repeated_wrong_passwords_are_rate_limited(client, alice):
    for _ in range(get_settings().login_max_failures):
        assert delete_account(client, alice, password="guess guess").status_code == 403
    response = delete_account(client, alice)  # even the right password, while blocked
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert client.get(ME, headers=alice.headers).status_code == 200


def test_last_owner_of_a_shared_document_is_refused(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    shared = make_document(alice, title="Shared NDA")
    share(client, alice, shared, bob, role="editor")
    make_document(alice, title="Private notes")  # alone: would be deleted, but not this time

    response = delete_account(client, alice)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["details"]["documents"] == [{"id": shared, "title": "Shared NDA"}]
    assert client.get(ME, headers=alice.headers).status_code == 200
    assert count(Document) == 2
    assert count(DocumentMember, DocumentMember.user_id == alice.id) == 2


# --- deletion: what happens ------------------------------------------------------------------


def test_deleting_removes_identity_and_leaves_a_placeholder(client, alice):
    response = delete_account(client, alice)

    assert response.status_code == 204
    assert 'sldm_session=""' in response.headers["set-cookie"]
    with SessionLocal() as db:
        user = db.get(User, alice.id)
        assert user.name == "Deleted user"
        assert user.email == f"deleted-user-{alice.id}@deleted.example"
        assert user.deleted_at is not None
        assert not verify_password(PASSWORD, user.password_hash)


def test_afterwards_tokens_and_sign_in_fail_and_the_email_is_free_again(client, alice):
    assert delete_account(client, alice).status_code == 204

    assert client.get(ME, headers=alice.headers).status_code == 401
    login = client.post("/api/auth/login", json={"email": alice.email, "password": PASSWORD})
    assert login.status_code == 401
    again = client.post(
        "/api/auth/register", json={"name": "Alice", "email": alice.email, "password": PASSWORD}
    )
    assert again.status_code == 201
    assert again.json()["user"]["id"] != alice.id


def test_a_deleted_account_cannot_sign_in_by_its_placeholder_email(client, alice):
    assert delete_account(client, alice).status_code == 204
    placeholder = f"deleted-user-{alice.id}@deleted.example"
    for password in (PASSWORD, ""):
        login = client.post("/api/auth/login", json={"email": placeholder, "password": password})
        assert login.status_code in (401, 422)


def test_documents_you_alone_belong_to_are_deleted(client, alice, make_document):
    private = make_document(alice, title="Private notes")

    assert delete_account(client, alice).status_code == 204

    assert count(Document, Document.id == private) == 0
    assert count(DocumentVersion, DocumentVersion.document_id == private) == 0


def test_you_leave_shared_documents_and_their_history_stays(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice, title="Lease")
    share(client, alice, document_id, bob, role="editor")
    add_version(client, bob, document_id, "Rent: 120.")

    assert delete_account(client, bob).status_code == 204

    members = client.get(f"/api/documents/{document_id}/members", headers=alice.headers).json()
    assert [m["user_id"] for m in members] == [alice.id]
    versions = client.get(f"/api/documents/{document_id}/versions", headers=alice.headers).json()
    assert [v["edited_by_name"] for v in versions] == ["Alice", "Deleted user"]
    activity = client.get(f"/api/documents/{document_id}/activity", headers=alice.headers).json()
    left = activity["items"][0]
    assert left["action"] == "member.removed"
    assert left["details"]["left"] is True
    assert left["actor_name"] == "Deleted user"


def test_a_co_owner_can_delete_their_account(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice, title="Joint venture")
    share(client, alice, document_id, bob, role="owner")

    assert delete_account(client, alice).status_code == 204

    members = client.get(f"/api/documents/{document_id}/members", headers=bob.headers).json()
    assert [(m["user_id"], m["role"]) for m in members] == [(bob.id, "owner")]


def test_your_notifications_are_deleted_but_others_keep_theirs(
    client, alice, signup, make_document
):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(bob, title="Bob's")
    share(client, bob, document_id, alice, role="editor")  # notifies Alice
    add_version(client, alice, document_id, "Alice's edit.")  # notifies Bob

    assert delete_account(client, alice).status_code == 204

    assert count(Notification, Notification.user_id == alice.id) == 0
    assert count(Notification, Notification.user_id == bob.id) == 1


def test_the_activity_log_is_not_rewritten(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice, title="Lease")
    share(client, alice, document_id, bob)
    before = count(ActivityEvent)

    assert delete_account(client, bob).status_code == 204

    assert count(ActivityEvent) == before + 1  # only the member.removed event is added


def test_deletion_is_logged_without_personal_data(client, alice, caplog):
    caplog.set_level(logging.INFO, logger="sldm")
    assert delete_account(client, alice).status_code == 204
    [record] = [r for r in caplog.records if getattr(r, "event", None) == "account_deleted"]
    logged = {key: value for key, value in record.fields.items() if key != "request_id"}
    assert logged == {"user_id": alice.id, "documents_deleted": 0, "documents_left": 0}


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_a_deleted_account_cannot_export_or_delete_again(client, alice, method):
    assert delete_account(client, alice).status_code == 204
    if method == "GET":
        response = client.get(EXPORT, headers=alice.headers)
    else:
        response = delete_account(client, alice)
    assert response.status_code == 401


def test_a_deleted_account_cannot_sign_in_even_with_a_known_password_hash(client, alice):
    # Second lock: e.g. a restored backup brings back a real hash. deleted_at alone refuses it.
    assert delete_account(client, alice).status_code == 204
    placeholder = f"deleted-user-{alice.id}@deleted.example"
    with SessionLocal() as db:
        db.get(User, alice.id).password_hash = hash_password(PASSWORD)
        db.commit()
    login = client.post("/api/auth/login", json={"email": placeholder, "password": PASSWORD})
    assert login.status_code == 401


@pytest.mark.parametrize("role", ["owner", "editor", "viewer"])
def test_a_deleted_account_cannot_be_added_to_a_document(
    client, alice, signup, make_document, role
):
    # Review finding M1: the placeholder email is predictable. Adding the placeholder as a
    # co-owner would let the real owner delete their account and leave a document nobody can open.
    bob = signup("Bob", "bob@example.com")
    assert delete_account(client, bob).status_code == 204
    document_id = make_document(alice)

    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": f"deleted-user-{bob.id}@deleted.example", "role": role},
        headers=alice.headers,
    )

    assert response.status_code == 404
    assert count(DocumentMember, DocumentMember.user_id == bob.id) == 0
    assert count(Notification, Notification.user_id == bob.id) == 0
