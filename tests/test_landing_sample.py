"""The landing page's sample history must be the demo's real history (Phase 9 F4).

The page shows clauses 3 and 4 of the sample Master Services Agreement at each version, with the
change from the version before marked. This keeps that excerpt true to `app/services/sample_data`:
text, authors and change notes. No invented proof (PRODUCT.md).
"""

import inspect
import json
import re
from pathlib import Path

from app.services import sample_data

HISTORY = Path(__file__).parent.parent / "frontend/src/pages/landing/msa-history.json"
# v4 restores v2, so its text is v2's.
VERSIONS = [sample_data.MSA_V1, sample_data.MSA_V2, sample_data.MSA_V3_REJECTED, sample_data.MSA_V2]


def clause(text: str, number: int) -> str:
    match = re.search(rf"^{number}\. .*?(?=\n\n|\Z)", text, flags=re.MULTILINE | re.DOTALL)
    assert match, f"clause {number} not found"
    return " ".join(match.group(0).split())


def joined(segments: list[list[str]], leave_out: str) -> str:
    return "".join(s[0] for s in segments if (s[1] if len(s) > 1 else None) != leave_out)


def folds() -> list[dict]:
    return json.loads(HISTORY.read_text())["folds"]


def test_each_fold_shows_its_versions_text_and_marks_the_change_from_the_one_before():
    for index, fold in enumerate(folds()):
        before = VERSIONS[index - 1] if index else VERSIONS[0]
        for position, number in enumerate((3, 4)):
            segments = fold["clauses"][position]
            assert joined(segments, leave_out="del") == clause(VERSIONS[index], number)
            assert joined(segments, leave_out="ins") == clause(before, number)


def test_the_title_authors_and_notes_are_the_seeded_ones():
    data = json.loads(HISTORY.read_text())
    source = inspect.getsource(sample_data)
    assert f'title="{data["title"]}"' in source
    authors = ["Asha Rao", "Chloe Martin", "Chloe Martin", "Asha Rao"]  # create, v2, v3, restore
    assert [f["author"] for f in folds()] == authors
    for fold in folds()[1:]:
        assert f'change_note="{fold["note"]}"' in source
    assert [f["state"] for f in folds()] == ["live", "live", "withdrawn", "restored"]
    assert "delete_version(db, msa, version_number=3" in source
    assert "restore_version(\n        db, msa, version_number=2" in source
