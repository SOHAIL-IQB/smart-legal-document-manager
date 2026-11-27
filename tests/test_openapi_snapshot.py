"""Phase 9 F2: the frontend's typed API client is generated from a committed snapshot of the API's
OpenAPI schema. This fails when the API changes and the snapshot wasn't refreshed, so the typed
client can never silently drift from the real API."""

from pathlib import Path

from scripts.export_openapi import SNAPSHOT, render

FIX = "run `python -m scripts.export_openapi`, then `npm run gen:api` in frontend/"


def test_the_committed_openapi_snapshot_matches_the_api():
    assert SNAPSHOT.exists(), f"missing {SNAPSHOT}: {FIX}"
    assert SNAPSHOT.read_text() == render(), f"the API changed: {FIX}"


def test_the_snapshot_lives_in_the_frontend():
    expected = Path(__file__).resolve().parents[1] / "frontend/src/api/openapi.json"
    assert expected == SNAPSHOT
