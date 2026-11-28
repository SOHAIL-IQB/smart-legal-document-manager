"""Phase 9 F1: a private demo workspace per visitor (spec D2; docs/specs/phase-9-frontend-build.md).

A reviewer with no account gets their own copy of the demo: three accounts and the four sample
contracts with history, sharing, activity and notifications. Workspaces are isolated from each
other and from real accounts, expire, and are rate-limited per IP.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    ActivityEvent,
    DemoWorkspace,
    Document,
    DocumentMember,
    DocumentVersion,
    Notification,
    User,
    utcnow,
)
from app.db.session import SessionLocal
from app.main import app
from app.services import demo as demo_service
from scripts import purge_demo, seed

CREATE = "/api/demo/workspaces"
SWITCH = "/api/demo/workspaces/current/switch"
XRW = {"X-Requested-With": "XMLHttpRequest"}


def create(client=None):
    response = (client or TestClient(app)).post(CREATE, headers=XRW)
    assert response.status_code == 201, response.text
    return response.json()


def bearer(body):
    return {"Authorization": f"Bearer {body['access_token']}", **XRW}


def count(model, *where):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where))


def expire(workspace_id):
    with SessionLocal() as db:
        db.get(DemoWorkspace, workspace_id).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()


# --- creating a workspace ----------------------------------------------------------------


def test_creating_a_workspace_signs_the_visitor_in_with_the_sample_contracts(client):
    body = create(client)

    assert body["user"]["name"] == "Asha Rao"
    assert [a["name"] for a in body["accounts"]] == ["Asha Rao", "Ben Carter", "Chloe Martin"]
    assert body["workspace"]["expires_at"]
    me = client.get("/api/auth/me", headers=bearer(body))
    assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]

    documents = client.get("/api/documents", headers=bearer(body)).json()
    assert documents["total"] == 4
    assert {d["my_role"] for d in documents["items"]} == {"owner", "editor", "viewer"}


def test_the_cookie_session_is_set_for_browsers(client):
    response = client.post(CREATE, headers=XRW)
    assert response.status_code == 201
    assert "sldm_session=" in response.headers["set-cookie"]
    assert "httponly" in response.headers["set-cookie"].lower()


def test_the_workspace_has_real_history_restores_deletions_and_notifications(client):
    body = create(client)
    with SessionLocal() as db:
        ids = [a["user_id"] for a in body["accounts"]]
        docs = db.scalars(select(Document.id).where(Document.created_by.in_(ids))).all()
        assert len(docs) == 4
        versions = select(func.count()).where(DocumentVersion.document_id.in_(docs))
        assert db.scalar(versions) >= 10
        restored = versions.where(DocumentVersion.source == "restore")
        assert db.scalar(restored) >= 1
        deleted = versions.where(DocumentVersion.deleted_at.is_not(None))
        assert db.scalar(deleted) >= 1
    assert count(Notification, Notification.user_id.in_(ids)) > 0


def test_creating_needs_the_csrf_header(client):
    response = client.post(CREATE)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert count(DemoWorkspace) == 0


def test_creation_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_workspaces_per_ip", 2)
    create(client)
    create(client)
    blocked = client.post(CREATE, headers=XRW)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.json()["error"]["details"]["retry_after"] > 0
    assert count(DemoWorkspace) == 2


# --- isolation ---------------------------------------------------------------------------


def test_two_workspaces_cannot_see_each_other(client):
    first, second = create(client), create(client)
    theirs = client.get("/api/documents", headers=bearer(second)).json()["items"][0]["id"]

    assert client.get(f"/api/documents/{theirs}", headers=bearer(first)).status_code == 404
    mine = {d["id"] for d in client.get("/api/documents", headers=bearer(first)).json()["items"]}
    assert theirs not in mine


def test_demo_accounts_cannot_sign_in_with_a_password(client):
    body = create(client)
    for account in body["accounts"]:
        for password in (seed.DEMO_PASSWORD, "correct horse battery"):
            login = client.post(
                "/api/auth/login", json={"email": account["email"], "password": password}
            )
            assert login.status_code == 401


def test_a_demo_account_cannot_sign_in_even_with_a_known_password_hash(client):
    # Second lock: the random hash already blocks sign-in; demo_workspace_id alone must too.
    body = create(client)
    asha = body["accounts"][0]
    with SessionLocal() as db:
        db.get(User, asha["user_id"]).password_hash = hash_password(seed.DEMO_PASSWORD)
        db.commit()
    login = client.post(
        "/api/auth/login", json={"email": asha["email"], "password": seed.DEMO_PASSWORD}
    )
    assert login.status_code == 401


def test_a_demo_account_cannot_share_with_a_real_account(client, alice):
    body = create(client)
    owned = next(
        d["id"]
        for d in client.get("/api/documents", headers=bearer(body)).json()["items"]
        if d["my_role"] == "owner"
    )
    response = client.post(
        f"/api/documents/{owned}/members",
        json={"email": alice.email, "role": "viewer"},
        headers=bearer(body),
    )
    assert response.status_code == 404
    assert count(DocumentMember, DocumentMember.user_id == alice.id) == 0


def test_a_real_account_cannot_share_with_a_demo_account(client, alice, make_document):
    body = create(client)
    document_id = make_document(alice)
    response = client.post(
        f"/api/documents/{document_id}/members",
        json={"email": body["accounts"][1]["email"], "role": "viewer"},
        headers=alice.headers,
    )
    assert response.status_code == 404
    assert count(DocumentMember, DocumentMember.document_id == document_id) == 1


def test_accounts_in_one_workspace_can_share_with_each_other(client, signup):
    body = create(client)
    owned = [
        d["id"]
        for d in client.get("/api/documents", headers=bearer(body)).json()["items"]
        if d["my_role"] == "owner"
    ]
    # Ben is not yet on every document Asha owns; adding him works inside the workspace.
    ben = body["accounts"][1]
    results = [
        client.post(
            f"/api/documents/{document_id}/members",
            json={"email": ben["email"], "role": "viewer"},
            headers=bearer(body),
        ).status_code
        for document_id in owned
    ]
    assert 201 in results


# --- the current workspace -----------------------------------------------------------------

CURRENT = "/api/demo/workspaces/current"


def test_a_demo_account_can_read_its_workspace_and_its_people(client):
    """The app header needs the other accounts after a reload, to offer the switch (Phase 9 F6)."""
    body = create(client)
    response = client.get(CURRENT, headers=bearer(body))
    assert response.status_code == 200
    current = response.json()
    assert current["workspace"] == body["workspace"]
    assert current["accounts"] == body["accounts"]
    assert [a["name"] for a in current["accounts"]] == ["Asha Rao", "Ben Carter", "Chloe Martin"]


def test_each_workspace_sees_only_its_own_people(client):
    first, second = create(client), create(client)
    theirs = {a["user_id"] for a in second["accounts"]}
    mine = client.get(CURRENT, headers=bearer(first)).json()["accounts"]
    assert not theirs & {a["user_id"] for a in mine}


def test_a_deleted_account_is_not_offered(client):
    body = create(client)
    ben = body["accounts"][1]["user_id"]
    with SessionLocal() as db:
        db.get(User, ben).deleted_at = utcnow()
        db.commit()
    names = [a["name"] for a in client.get(CURRENT, headers=bearer(body)).json()["accounts"]]
    assert names == ["Asha Rao", "Chloe Martin"]


def test_a_real_account_has_no_demo_workspace(client, alice):
    response = client.get(CURRENT, headers=alice.headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_reading_the_workspace_needs_a_session(client):
    assert client.get(CURRENT).status_code == 401


def test_an_expired_workspace_cannot_be_read(client):
    body = create(client)
    expire(body["workspace"]["id"])
    assert client.get(CURRENT, headers=bearer(body)).status_code == 401


# --- switching accounts --------------------------------------------------------------------


def test_switching_to_another_account_of_the_same_workspace(client):
    body = create(client)
    ben = body["accounts"][1]

    response = client.post(SWITCH, json={"user_id": ben["user_id"]}, headers=bearer(body))

    assert response.status_code == 200
    switched = response.json()
    assert switched["user"]["name"] == "Ben Carter"
    me = client.get("/api/auth/me", headers=bearer(switched)).json()
    assert me["id"] == ben["user_id"]


def test_switching_to_an_account_of_another_workspace_is_refused(client):
    first, second = create(client), create(client)
    stranger = second["accounts"][1]["user_id"]
    response = client.post(SWITCH, json={"user_id": stranger}, headers=bearer(first))
    assert response.status_code == 404


def test_switching_to_a_deleted_account_is_refused(client):
    body = create(client)
    chloe = body["accounts"][2]
    with SessionLocal() as db:
        db.get(User, chloe["user_id"]).deleted_at = utcnow()
        db.commit()
    response = client.post(SWITCH, json={"user_id": chloe["user_id"]}, headers=bearer(body))
    assert response.status_code == 404


def test_a_real_account_cannot_switch(client, alice, signup):
    bob = signup("Bob", "bob@example.com")
    response = client.post(SWITCH, json={"user_id": bob.id}, headers={**alice.headers, **XRW})
    assert response.status_code == 403


# --- expiry and purge --------------------------------------------------------------------


def test_an_expired_workspace_stops_working_before_the_purge(client):
    body = create(client)
    expire(body["workspace"]["id"])
    assert client.get("/api/auth/me", headers=bearer(body)).status_code == 401


def test_purge_removes_everything_in_expired_workspaces_and_nothing_else(
    client, alice, make_document
):
    kept_document = make_document(alice)
    expired, current = create(client), create(client)
    expire(expired["workspace"]["id"])
    gone = [a["user_id"] for a in expired["accounts"]]
    kept = [a["user_id"] for a in current["accounts"]]

    with SessionLocal() as db:
        assert demo_service.purge_expired(db) == 1

    assert count(DemoWorkspace) == 1
    assert count(User, User.id.in_(gone)) == 0
    assert count(Document, Document.created_by.in_(gone)) == 0
    assert count(Notification, Notification.user_id.in_(gone)) == 0
    assert count(Notification, Notification.actor_id.in_(gone)) == 0
    assert count(ActivityEvent, ActivityEvent.actor_id.in_(gone)) == 0
    assert count(User, User.id.in_(kept)) == 3
    assert count(Document, Document.created_by.in_(kept)) == 4
    assert count(Document, Document.id == kept_document) == 1


def test_purge_succeeds_even_if_a_demo_account_notified_a_real_one(client, alice):
    # Isolation should prevent this row; if one ever exists (old data, a future bug), a stray
    # notification must not block the purge with a foreign-key error and keep the workspace alive.
    body = create(client)
    with SessionLocal() as db:
        db.add(
            Notification(
                user_id=alice.id,
                actor_id=body["accounts"][1]["user_id"],
                kind="version_created",
                message="Ben Carter saved version 2.",
            )
        )
        db.commit()
    expire(body["workspace"]["id"])

    with SessionLocal() as db:
        assert demo_service.purge_expired(db) == 1

    assert count(Notification, Notification.user_id == alice.id) == 0
    assert count(User, User.id == alice.id) == 1


def test_creating_a_workspace_also_purges_expired_ones(client):
    old = create(client)
    expire(old["workspace"]["id"])
    create(client)
    # Not by id: SQLite may hand the purged id to the new workspace (Postgres never reuses ids).
    assert count(DemoWorkspace, DemoWorkspace.expires_at <= utcnow()) == 0
    assert count(DemoWorkspace) == 1


def test_the_purge_script_reports_what_it_removed(client, capsys):
    expire(create(client)["workspace"]["id"])
    purge_demo.main()
    assert "Removed 1 expired demo workspace" in capsys.readouterr().out


# --- the seed still works the same way ----------------------------------------------------


def test_seed_and_workspace_share_one_definition_of_the_sample_contracts(client):
    seed.run()
    body = create(client)
    with SessionLocal() as db:
        titles = sorted(
            db.scalars(
                select(Document.title).where(
                    Document.created_by.in_([a["user_id"] for a in body["accounts"]])
                )
            ).all()
        )
        seeded = sorted(
            db.scalars(
                select(Document.title)
                .join(User, User.id == Document.created_by)
                .where(User.demo_workspace_id.is_(None))
            ).all()
        )
    assert titles == seeded


@pytest.mark.parametrize("hours", [24])
def test_workspaces_last_the_configured_time(client, hours):
    body = create(client)
    with SessionLocal() as db:
        workspace = db.get(DemoWorkspace, body["workspace"]["id"])
        assert workspace.expires_at - workspace.created_at == timedelta(hours=hours)
