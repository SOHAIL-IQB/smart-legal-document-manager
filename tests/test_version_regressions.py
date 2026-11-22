"""Phase 3 regression tests for audit defects B2, B3, B4.

Written before the fix and run against the old code first (see LOG.md entry 006).
"""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app

ON_POSTGRES = os.environ.get("DATABASE_URL", "").startswith("postgresql")


def add_version(client, account, document_id, content):
    return client.post(
        f"/api/documents/{document_id}/versions", json={"content": content}, headers=account.headers
    )


def test_b2_version_numbers_are_never_reused(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    assert add_version(client, alice, document_id, "v2").json()["version"] == 2

    deleted = client.delete(f"/api/documents/{document_id}/versions/2", headers=alice.headers)
    assert deleted.status_code == 200

    # The next version must be 3, not a second "version 2" with different content.
    assert add_version(client, alice, document_id, "v3").json()["version"] == 3


def test_b3_the_last_remaining_version_cannot_be_deleted(client, alice, make_document):
    document_id = make_document(alice, content="only version")

    response = client.delete(f"/api/documents/{document_id}/versions/1", headers=alice.headers)

    assert response.status_code == 409
    # The document stays editable.
    assert add_version(client, alice, document_id, "still editable").status_code == 201


@pytest.mark.skipif(
    not ON_POSTGRES,
    reason="Needs real row locks; runs with TEST_DATABASE_URL=postgresql... (and in CI)",
)
def test_b4_concurrent_saves_get_distinct_numbers_and_no_errors(alice, make_document):
    document_id = make_document(alice, content="v1")
    writers = 8

    def save(i: int):
        with TestClient(app, raise_server_exceptions=False) as client:
            return add_version(client, alice, document_id, f"draft from writer {i}")

    with ThreadPoolExecutor(max_workers=writers) as pool:
        responses = list(pool.map(save, range(writers)))

    assert [r.status_code for r in responses] == [201] * writers
    numbers = sorted(r.json()["version"] for r in responses)
    assert numbers == list(range(2, writers + 2))
