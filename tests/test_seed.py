"""Phase 7 T10: the demo seed creates realistic data, is safe to re-run, and refuses production."""

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import (
    ActivityEvent,
    Document,
    DocumentMember,
    DocumentVersion,
    Notification,
    User,
)
from app.db.session import SessionLocal
from scripts import seed


def counts():
    with SessionLocal() as db:
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in (
                User,
                Document,
                DocumentMember,
                DocumentVersion,
                ActivityEvent,
                Notification,
            )
        }


def test_seed_creates_users_contracts_history_and_sharing():
    created = seed.run()
    assert created is True
    totals = counts()
    assert totals["users"] == 3
    assert totals["documents"] == 4
    assert totals["document_versions"] >= 10
    assert totals["notifications"] > 0
    with SessionLocal() as db:
        roles = set(db.scalars(select(DocumentMember.role)))
        assert roles == {"owner", "editor", "viewer"}
        assert db.scalar(select(func.count()).where(DocumentVersion.deleted_at.is_not(None))) >= 1
        assert db.scalar(select(func.count()).where(DocumentVersion.source == "restore")) >= 1


def test_demo_users_can_sign_in_and_see_shared_documents(client):
    seed.run()
    for account in seed.DEMO_USERS:
        response = client.post(
            "/api/auth/login", json={"email": account.email, "password": seed.DEMO_PASSWORD}
        )
        assert response.status_code == 200, account.email
        token = response.json()["access_token"]
        listing = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
        assert listing.json()["total"] >= 1


def test_running_the_seed_twice_adds_nothing():
    seed.run()
    before = counts()
    assert seed.run() is False
    assert counts() == before


def test_seed_refuses_to_run_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(SystemExit, match="production"):
        seed.run()
    assert counts()["users"] == 0
