"""Write the API's OpenAPI schema to frontend/src/api/openapi.json (Phase 9 F2).

    python -m scripts.export_openapi

The frontend generates its typed client from this snapshot (`npm run gen:api` in frontend/).
tests/test_openapi_snapshot.py fails when the API changes without this being rerun.
"""

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[1] / "frontend/src/api/openapi.json"


def render() -> str:
    """The schema as stable text: sorted keys, so a diff shows only real API changes."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(render())
    print("Wrote frontend/src/api/openapi.json")


if __name__ == "__main__":
    main()
