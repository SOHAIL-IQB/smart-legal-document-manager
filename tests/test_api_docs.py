"""Phase 7 T9: the README's endpoint table must match the running API exactly.

documentation-and-adrs: a doc that drifts from the code still reads as authoritative, so the
table is checked against the app's own OpenAPI schema on every test run.
"""

import re
from pathlib import Path

from app.main import app

README = Path(__file__).resolve().parents[1] / "README.md"
PLACEHOLDER = re.compile(r"\{[^}]*\}")


def _normalize(path: str) -> str:
    path = path.split("?")[0].rstrip("/")
    return PLACEHOLDER.sub("{}", path)


def documented_endpoints() -> set[tuple[str, str]]:
    text = README.read_text()
    section = text.split("## API Endpoints", 1)[1].split("\n## ", 1)[0]
    endpoints = set()
    for row in section.splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0].startswith("`"):
            continue
        methods = re.findall(r"`([A-Z]+)`", cells[0])
        paths = [p for p in re.findall(r"`([^`]+)`", cells[1]) if p.startswith("/")]
        for method in methods:
            for path in paths:
                endpoints.add((method, "/api" + _normalize(path)))
    return endpoints


def actual_endpoints() -> set[tuple[str, str]]:
    return {
        (method.upper(), _normalize(path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def test_readme_documents_every_endpoint_and_nothing_else():
    documented, actual = documented_endpoints(), actual_endpoints()
    assert actual - documented == set(), "in the API but missing from README"
    assert documented - actual == set(), "in README but not in the API"


def test_readme_error_shape_mentions_the_request_id():
    assert '"request_id"' in README.read_text().split("## API Endpoints", 1)[1]
