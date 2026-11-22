import os
from collections.abc import Callable
from dataclasses import dataclass
from itertools import count
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).parent / "test.db"

# Must be set before the app (and its engine) is imported.
os.environ["ENVIRONMENT"] = "test"
# SQLite by default (fast); set TEST_DATABASE_URL to run the same suite against Postgres.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
os.environ["CORS_ORIGINS"] = '["http://localhost:5173"]'

from app.core.security import login_rate_limiter  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "correct horse battery"


@dataclass(frozen=True)
class Account:
    id: int
    name: str
    email: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture(autouse=True)
def reset_state():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_rate_limiter.reset()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def signup(client) -> Callable[..., Account]:
    """Register an account and return its id and bearer token."""
    numbers = count(1)

    def _signup(name: str = "Alice", email: str | None = None) -> Account:
        email = email or f"user{next(numbers)}@example.com"
        response = TestClient(app).post(
            "/api/auth/register", json={"name": name, "email": email, "password": PASSWORD}
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return Account(body["user"]["id"], name, email, body["access_token"])

    return _signup


@pytest.fixture()
def alice(signup) -> Account:
    return signup("Alice", "alice@example.com")


@pytest.fixture()
def make_document(client) -> Callable[..., int]:
    def _make(
        owner: Account, title: str = "Service Agreement", content: str = "Term: 1 year."
    ) -> int:
        response = client.post(
            "/api/documents", json={"title": title, "content": content}, headers=owner.headers
        )
        assert response.status_code == 201, response.text
        return response.json()["document_id"]

    return _make
