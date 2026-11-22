"""Phase 2: registration, login, sessions, CSRF and rate limiting (B1, B14). See ADR 0001."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import DEV_SECRET_KEY, Settings, get_settings
from app.db.models import User
from app.db.session import SessionLocal
from app.main import app
from tests.conftest import PASSWORD

COOKIE = "sldm_session"
CSRF = {"X-Requested-With": "XMLHttpRequest"}


def register(client, email="bob@example.com", password=PASSWORD, name="Bob"):
    return client.post(
        "/api/auth/register", json={"name": name, "email": email, "password": password}
    )


def login(client, email="bob@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# --- registration ------------------------------------------------------------


def test_register_returns_user_and_token_and_sets_secure_cookie(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "bob@example.com"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 12 * 60 * 60
    assert "password" not in response.text and "password_hash" not in response.text

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=43200" in cookie


def test_password_is_stored_as_argon2_hash(client):
    register(client)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "bob@example.com"))
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length_is_enforced(client, password):
    assert register(client, password=password).status_code == 422


def test_duplicate_email_is_conflict_case_insensitive(client):
    register(client, email="bob@example.com")
    response = register(client, email="BOB@Example.com")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_user_list_endpoint_no_longer_exists(client, alice):
    assert client.get("/api/users", headers=alice.headers).status_code == 404


# --- login -------------------------------------------------------------------


def test_login_with_correct_password(client):
    register(client)
    response = login(TestClient(app))
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "bob@example.com"


def test_login_email_is_case_insensitive(client):
    register(client)
    assert login(client, email="Bob@Example.COM").status_code == 200


def test_wrong_password_and_unknown_email_give_identical_errors(client):
    register(client)
    wrong_password = login(client, password="not the password")
    unknown_email = login(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_is_rate_limited_after_repeated_failures(client):
    register(client)
    limit = get_settings().login_max_failures
    for _ in range(limit):
        assert login(client, password="wrong password").status_code == 401

    blocked = login(client)  # even the right password is refused while blocked
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.json()["error"]["details"]["retry_after"] > 0

    # A different email from the same client isn't blocked.
    register(client, email="carol@example.com", name="Carol")
    assert login(client, email="carol@example.com").status_code == 200


def test_successful_login_resets_failure_count(client):
    register(client)
    limit = get_settings().login_max_failures
    for _ in range(limit - 1):
        login(client, password="wrong password")
    assert login(client).status_code == 200
    for _ in range(limit - 1):
        login(client, password="wrong password")
    assert login(client).status_code == 200


# --- sessions ------------------------------------------------------------------


def test_me_with_bearer_token(client, alice):
    response = client.get("/api/auth/me", headers=alice.headers)
    assert response.status_code == 200
    assert response.json()["id"] == alice.id


def test_me_with_cookie(client):
    register(client)  # TestClient keeps the cookie
    assert client.get("/api/auth/me").json()["email"] == "bob@example.com"


def test_logout_clears_cookie(client):
    register(client)
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert f'{COOKIE}=""' in response.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 401


def test_protected_route_without_credentials_is_401(client):
    response = client.get("/api/documents")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def _token(user_id, *, minutes=5, key=DEV_SECRET_KEY, typ="access", **extra):
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "typ": typ, "iat": now, "exp": now + timedelta(minutes=minutes)}
    claims.update(extra)
    return jwt.encode(claims, key, algorithm="HS256")


@pytest.mark.parametrize(
    "make_token",
    [
        pytest.param(lambda uid: _token(uid, minutes=-1), id="expired"),
        pytest.param(lambda uid: _token(uid, key="x" * 40), id="wrong-signature"),
        pytest.param(lambda uid: _token(uid, typ="refresh"), id="wrong-type"),
        pytest.param(lambda uid: _token(uid + 999), id="unknown-user"),
        pytest.param(lambda uid: _token(uid) + "tampered", id="tampered"),
        pytest.param(lambda uid: jwt.encode({"sub": str(uid)}, DEV_SECRET_KEY), id="no-exp"),
        pytest.param(lambda uid: _token("abc"), id="non-numeric-sub"),
        pytest.param(lambda uid: "not-a-jwt", id="garbage"),
    ],
)
def test_invalid_tokens_are_rejected(client, alice, make_token):
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {make_token(alice.id)}"}
    )
    assert response.status_code == 401


def test_alg_none_token_is_rejected(client, alice):
    unsigned = jwt.encode(
        {"sub": str(alice.id), "typ": "access", "iat": 0, "exp": 9_999_999_999},
        key=None,
        algorithm="none",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"})
    assert response.status_code == 401


# --- CSRF ----------------------------------------------------------------------


def test_cookie_auth_write_without_csrf_header_is_refused(client):
    register(client)
    response = client.post("/api/documents", json={"title": "T", "content": "c"})
    assert response.status_code == 403
    assert "X-Requested-With" in response.json()["error"]["message"]


def test_cookie_auth_write_with_csrf_header_is_allowed(client):
    register(client)
    response = client.post("/api/documents", json={"title": "T", "content": "c"}, headers=CSRF)
    assert response.status_code == 201


def test_cookie_auth_reads_do_not_need_csrf_header(client):
    register(client)
    assert client.get("/api/documents").status_code == 200


def test_bearer_auth_writes_do_not_need_csrf_header(client, alice):
    response = client.post(
        "/api/documents", json={"title": "T", "content": "c"}, headers=alice.headers
    )
    assert response.status_code == 201


# --- configuration ---------------------------------------------------------------


def test_production_refuses_default_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production")


def test_production_refuses_short_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", secret_key="too-short")


def test_production_accepts_strong_secret_and_marks_cookie_secure():
    settings = Settings(environment="production", secret_key="s" * 48)
    assert settings.cookie_secure is True
