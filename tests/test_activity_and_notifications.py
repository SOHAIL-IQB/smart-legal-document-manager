"""Phase 6: the append-only activity log and the notification inbox."""

import pytest
from sqlalchemy import select

from app.db.models import ActivityEvent, Notification
from app.db.session import SessionLocal
from tests.files import make_pdf


def share(client, owner, document_id, member, role="editor"):
    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": member.email, "role": role},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text


def add_version(client, account, document_id, content, **extra):
    return client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": content, **extra},
        headers=account.headers,
    )


def activity(client, account, document_id, **params):
    response = client.get(
        f"/api/documents/{document_id}/activity", params=params, headers=account.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def inbox(client, account, **params):
    response = client.get("/api/notifications", params=params, headers=account.headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def bob(signup):
    return signup("Bob", "bob@example.com")


@pytest.fixture()
def carol(signup):
    return signup("Carol", "carol@example.com")


# --- activity log ---------------------------------------------------------------------


def test_every_action_is_recorded_newest_first_with_actor(client, alice, bob, make_document):
    document_id = make_document(alice, title="NDA", content="v1")
    share(client, alice, document_id, bob, "viewer")
    client.patch(
        f"/api/documents/{document_id}/members/{bob.id}",
        json={"role": "editor"},
        headers=alice.headers,
    )
    add_version(client, bob, document_id, "v2", change_note="Tightened")
    client.post(f"/api/documents/{document_id}/versions/1/restore", headers=alice.headers)
    client.patch(
        f"/api/documents/{document_id}/title", json={"title": "NDA v2"}, headers=bob.headers
    )
    client.delete(f"/api/documents/{document_id}/versions/2", headers=alice.headers)
    client.delete(f"/api/documents/{document_id}/members/{bob.id}", headers=bob.headers)

    body = activity(client, alice, document_id)
    actions = [(e["action"], e["actor_name"]) for e in body["items"]]

    assert actions == [
        ("member.removed", "Bob"),
        ("version.deleted", "Alice"),
        ("document.renamed", "Bob"),
        ("version.restored", "Alice"),
        ("version.created", "Bob"),
        ("member.role_changed", "Alice"),
        ("member.added", "Alice"),
        ("document.created", "Alice"),
    ]
    assert body["total"] == 8


def test_event_details(client, alice, bob, make_document):
    document_id = make_document(alice, title="NDA", content="v1")
    share(client, alice, document_id, bob, "viewer")
    client.patch(
        f"/api/documents/{document_id}/members/{bob.id}",
        json={"role": "editor"},
        headers=alice.headers,
    )
    add_version(client, bob, document_id, "v2", change_note="Tightened")
    client.post(f"/api/documents/{document_id}/versions/1/restore", headers=alice.headers)
    client.patch(
        f"/api/documents/{document_id}/title", json={"title": "NDA v2"}, headers=bob.headers
    )
    client.delete(f"/api/documents/{document_id}/versions/2", headers=alice.headers)
    client.delete(f"/api/documents/{document_id}/members/{bob.id}", headers=bob.headers)

    events = {e["action"]: e["details"] for e in activity(client, alice, document_id)["items"]}

    assert events["document.created"] == {"title": "NDA", "version": 1, "source": "manual"}
    assert events["member.added"] == {"user_id": bob.id, "name": "Bob", "role": "viewer"}
    assert events["member.role_changed"] == {
        "user_id": bob.id,
        "name": "Bob",
        "from": "viewer",
        "to": "editor",
    }
    assert events["version.created"] == {
        "version": 2,
        "source": "manual",
        "change_note": "Tightened",
        "meaningful": True,
    }
    assert events["version.restored"]["restored_from"] == 1
    assert events["version.restored"]["version"] == 3
    assert events["document.renamed"] == {"from": "NDA", "to": "NDA v2"}
    assert events["version.deleted"] == {"version": 2}
    assert events["member.removed"] == {"user_id": bob.id, "name": "Bob", "left": True}


def test_uploads_record_the_file_name(client, alice):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("Lease.pdf", make_pdf("Rent."), "application/pdf")},
        headers=alice.headers,
    )
    document_id = response.json()["document_id"]
    [created] = activity(client, alice, document_id)["items"]
    assert created["details"]["source"] == "upload"
    assert created["details"]["source_filename"] == "Lease.pdf"


def test_identical_save_records_nothing(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    assert add_version(client, alice, document_id, "v1").status_code == 200
    assert activity(client, alice, document_id)["total"] == 1  # just document.created


def test_failed_actions_record_nothing(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    # Deleting the only version is refused (409); no event may be left behind.
    assert (
        client.delete(f"/api/documents/{document_id}/versions/1", headers=alice.headers).status_code
        == 409
    )
    assert [e["action"] for e in activity(client, alice, document_id)["items"]] == [
        "document.created"
    ]


def test_activity_is_paginated(client, alice, make_document):
    document_id = make_document(alice, content="v0")
    for i in range(1, 6):
        add_version(client, alice, document_id, f"v{i}")
    page = activity(client, alice, document_id, limit=2, offset=1)
    assert page["total"] == 6
    assert [e["details"]["version"] for e in page["items"]] == [5, 4]


def test_activity_needs_membership(client, alice, bob, make_document):
    document_id = make_document(alice)
    response = client.get(f"/api/documents/{document_id}/activity", headers=bob.headers)
    assert response.status_code == 404


def test_viewers_can_read_activity(client, alice, bob, make_document):
    document_id = make_document(alice)
    share(client, alice, document_id, bob, "viewer")
    assert activity(client, bob, document_id)["total"] == 2


def test_activity_events_cannot_be_modified(client, alice, make_document):
    make_document(alice)
    with SessionLocal() as db:
        event = db.scalars(select(ActivityEvent)).first()
        event.action = "document.tampered"
        with pytest.raises(PermissionError, match="append-only"):
            db.commit()


@pytest.mark.parametrize("method", ["PATCH", "PUT", "DELETE"])
def test_there_is_no_endpoint_to_change_activity(client, alice, make_document, method):
    document_id = make_document(alice)
    response = client.request(
        method, f"/api/documents/{document_id}/activity", headers=alice.headers
    )
    assert response.status_code == 405


# --- notifications ----------------------------------------------------------------------


def test_meaningful_version_notifies_other_members_but_not_the_editor(
    client, alice, bob, carol, make_document
):
    document_id = make_document(alice, title="NDA", content="Clause A")
    share(client, alice, document_id, bob)
    share(client, alice, document_id, carol, "viewer")

    add_version(client, bob, document_id, "Clause A, amended")

    for recipient in (alice, carol):
        [item] = [n for n in inbox(client, recipient)["items"] if n["kind"] == "version_created"]
        assert item["message"] == "Bob saved version 2 of “NDA”."
        assert item["document_id"] == document_id
        assert item["version_number"] == 2
        assert item["actor_name"] == "Bob"
        assert item["read_at"] is None
    assert [n for n in inbox(client, bob)["items"] if n["kind"] == "version_created"] == []


def test_whitespace_only_version_notifies_nobody(client, alice, bob, make_document):
    document_id = make_document(alice, content="Clause A\nClause B")
    share(client, alice, document_id, bob)
    assert add_version(client, alice, document_id, "Clause A \nClause B").status_code == 201
    assert [n for n in inbox(client, bob)["items"] if n["kind"] == "version_created"] == []


def test_restore_and_upload_notify_like_any_version(client, alice, bob, make_document):
    document_id = make_document(alice, title="NDA", content="A")
    share(client, alice, document_id, bob)
    add_version(client, alice, document_id, "B")
    client.post(f"/api/documents/{document_id}/versions/1/restore", headers=alice.headers)
    client.post(
        f"/api/documents/{document_id}/versions/upload",
        files={"file": ("v4.txt", b"C", "text/plain")},
        headers=alice.headers,
    )
    versions = sorted(
        n["version_number"] for n in inbox(client, bob)["items"] if n["kind"] == "version_created"
    )
    assert versions == [2, 3, 4]


def test_sharing_role_change_and_removal_notify_the_member(client, alice, bob, make_document):
    document_id = make_document(alice, title="Lease")
    share(client, alice, document_id, bob, "viewer")
    client.patch(
        f"/api/documents/{document_id}/members/{bob.id}",
        json={"role": "editor"},
        headers=alice.headers,
    )
    client.delete(f"/api/documents/{document_id}/members/{bob.id}", headers=alice.headers)

    messages = [(n["kind"], n["message"]) for n in inbox(client, bob)["items"]]
    assert messages == [
        ("removed_from_document", "Alice removed you from “Lease”."),
        ("role_changed", "Alice changed your role on “Lease” to editor."),
        ("document_shared", "Alice shared “Lease” with you as viewer."),
    ]


def test_leaving_a_document_notifies_nobody(client, alice, bob, make_document):
    document_id = make_document(alice)
    share(client, alice, document_id, bob)
    client.delete(f"/api/documents/{document_id}/members/{bob.id}", headers=bob.headers)
    assert [n["kind"] for n in inbox(client, bob)["items"]] == ["document_shared"]
    assert inbox(client, alice)["total"] == 0


def test_deleted_document_notification_survives_the_document(client, alice, bob, make_document):
    document_id = make_document(alice, title="Old NDA", content="A")
    share(client, alice, document_id, bob)
    add_version(client, alice, document_id, "B")

    client.delete(f"/api/documents/{document_id}?confirm=true", headers=alice.headers)

    items = inbox(client, bob)["items"]
    assert items[0]["kind"] == "document_deleted"
    assert items[0]["message"] == "Alice deleted “Old NDA”."
    assert items[0]["document_id"] is None
    assert {n["document_id"] for n in items} == {None}  # earlier notifications are kept too


def test_unread_count_mark_one_and_mark_all(client, alice, bob, make_document):
    document_id = make_document(alice, content="A")
    share(client, alice, document_id, bob)
    for content in ("B", "C"):
        add_version(client, alice, document_id, content)

    count = client.get("/api/notifications/unread-count", headers=bob.headers).json()
    assert count == {"unread": 3}  # shared + 2 versions

    first = inbox(client, bob)["items"][0]["id"]
    marked = client.post(f"/api/notifications/{first}/read", headers=bob.headers)
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert inbox(client, bob, unread_only="true")["total"] == 2

    assert client.post("/api/notifications/read-all", headers=bob.headers).json() == {"updated": 2}
    assert client.get("/api/notifications/unread-count", headers=bob.headers).json() == {
        "unread": 0
    }


def test_marking_read_twice_keeps_the_first_time(client, alice, bob, make_document):
    document_id = make_document(alice)
    share(client, alice, document_id, bob)
    item = inbox(client, bob)["items"][0]["id"]
    first = client.post(f"/api/notifications/{item}/read", headers=bob.headers).json()["read_at"]
    second = client.post(f"/api/notifications/{item}/read", headers=bob.headers).json()["read_at"]
    assert first == second


def test_cannot_read_or_mark_someone_elses_notification(client, alice, bob, make_document):
    document_id = make_document(alice)
    share(client, alice, document_id, bob)
    bobs = inbox(client, bob)["items"][0]["id"]
    assert client.post(f"/api/notifications/{bobs}/read", headers=alice.headers).status_code == 404
    assert inbox(client, alice)["total"] == 0


def test_inbox_is_paginated_newest_first(client, alice, bob, make_document):
    document_id = make_document(alice, content="v0")
    share(client, alice, document_id, bob)
    for i in range(1, 5):
        add_version(client, alice, document_id, f"v{i}")
    page = inbox(client, bob, limit=2, offset=0)
    assert page["total"] == 5
    assert page["unread"] == 5
    assert [n["version_number"] for n in page["items"]] == [5, 4]


def test_notifications_require_sign_in(client):
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401


def test_every_timestamp_the_api_returns_has_a_timezone(client, alice, bob, make_document):
    document_id = make_document(alice)
    share(client, alice, document_id, bob)
    add_version(client, alice, document_id, "changed")
    item = inbox(client, bob)["items"][0]
    marked = client.post(f"/api/notifications/{item['id']}/read", headers=bob.headers).json()
    stamps = [
        client.get(f"/api/documents/{document_id}", headers=alice.headers).json()["created_at"],
        client.get(f"/api/documents/{document_id}/versions/1", headers=alice.headers).json()[
            "created_at"
        ],
        activity(client, alice, document_id)["items"][0]["created_at"],
        item["created_at"],
        marked["read_at"],
    ]
    assert all(s.endswith(("Z", "+00:00")) for s in stamps), stamps


def test_long_names_and_titles_still_fit_the_notification_message(client, signup):
    # Review finding M3: name (up to 255) + title (up to 255) + text passed the 500-character
    # column. Postgres refused the row, so sharing, and every later save, failed with a 500.
    owner = signup("N" * 255, "long-owner@example.com")
    editor = signup("E" * 255, "long-editor@example.com")
    created = client.post(
        "/api/documents", json={"title": "T" * 255, "content": "v1"}, headers=owner.headers
    )
    document_id = created.json()["document_id"]

    share(client, owner, document_id, editor, role="editor")
    add_version(client, editor, document_id, "v2")
    role_change = client.patch(
        f"/api/documents/{document_id}/members/{editor.id}",
        json={"role": "viewer"},
        headers=owner.headers,
    )
    assert role_change.status_code == 200
    deleted = client.delete(f"/api/documents/{document_id}?confirm=true", headers=owner.headers)
    assert deleted.status_code == 200

    with SessionLocal() as db:
        messages = db.scalars(select(Notification.message)).all()
    assert len(messages) == 4  # shared, new version, role changed, deleted
    assert all(len(message) <= 500 for message in messages)
    assert all(message.endswith(("…", ".")) for message in messages)
