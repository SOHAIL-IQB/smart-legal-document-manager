"""Phase 9: GET /auth/session answers "who is signed in?" without treating "nobody" as an error.

The frontend asks this on every visit. /auth/me answers 401 when signed out, which browsers log as a
console error on every signed-out page view; this endpoint answers 200 with `user: null` instead,
and applies exactly the same rules as /auth/me for who counts as signed in.
"""

from datetime import timedelta

import pytest

from app.db.models import DemoWorkspace, User, utcnow
from app.db.session import SessionLocal
from tests.test_auth import COOKIE, CSRF, _token, register

SESSION = "/api/auth/session"


def test_signed_out_is_200_with_no_user(client):
    response = client.get(SESSION)
    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_me_is_still_401_when_signed_out(client):
    assert client.get("/api/auth/me").status_code == 401


def test_bearer_token_gives_the_same_user_as_me(client, alice):
    response = client.get(SESSION, headers=alice.headers)
    assert response.status_code == 200
    assert response.json() == {"user": client.get("/api/auth/me", headers=alice.headers).json()}


def test_cookie_gives_the_user(client):
    register(client)  # TestClient keeps the cookie
    assert client.get(SESSION).json()["user"]["email"] == "bob@example.com"


@pytest.mark.parametrize(
    "make_token",
    [
        pytest.param(lambda uid: _token(uid, minutes=-1), id="expired"),
        pytest.param(lambda uid: _token(uid, key="x" * 40), id="wrong-signature"),
        pytest.param(lambda uid: _token(uid + 999), id="unknown-user"),
        pytest.param(lambda uid: "not-a-jwt", id="garbage"),
    ],
)
def test_an_invalid_token_counts_as_signed_out(client, alice, make_token):
    response = client.get(SESSION, headers={"Authorization": f"Bearer {make_token(alice.id)}"})
    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_an_invalid_cookie_counts_as_signed_out(client):
    client.cookies.set(COOKIE, "not-a-jwt")
    assert client.get(SESSION).json() == {"user": None}


def test_a_deleted_account_counts_as_signed_out(client, alice):
    with SessionLocal() as db:
        db.get(User, alice.id).deleted_at = utcnow()
        db.commit()
    assert client.get(SESSION, headers=alice.headers).json() == {"user": None}


def test_an_expired_demo_workspace_counts_as_signed_out(client):
    body = client.post("/api/demo/workspaces", headers=CSRF).json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get(SESSION, headers=headers).json()["user"] is not None

    with SessionLocal() as db:
        db.get(DemoWorkspace, body["workspace"]["id"]).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get(SESSION, headers=headers).json() == {"user": None}
