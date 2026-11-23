"""The floor guard: each move that lowers the bar fails, clean and tightening changes pass,
and a guard that cannot run exits 2 (never 0)."""

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "floor_guard.py"

BASE_TEST = """def test_total():
    assert add(1, 2) == 3
    assert add(0, 0) == 0
"""
BASE_CONSTRAINTS = """# Constraints

| Dimension | Rule | Checked by |
|---|---|---|
| Coverage | must not fall below 97.5% | pytest |
| Latency | p95 at most 200 ms | bench |

## Exceptions

| ID | Rule | Path | Reason | Owner | Expires |
|----|------|------|--------|-------|---------|
"""


def run(cmd, cwd):
    # Fixed argument lists built in this file (exception W2 in CONSTRAINTS.md).
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603


@pytest.fixture()
def repo(tmp_path):
    def git(*args):
        result = run(["git", *args], tmp_path)
        assert result.returncode == 0, result.stderr

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_app.py").write_text(BASE_TEST)
    (tmp_path / "CONSTRAINTS.md").write_text(BASE_CONSTRAINTS)
    git("add", ".")
    git("commit", "-q", "-m", "base")
    return tmp_path


def guard(repo, base="HEAD"):
    return run([sys.executable, str(GUARD), "--base", base], repo)


def edit(repo, name, old, new):
    path = repo / name
    path.write_text(path.read_text().replace(old, new))


def test_clean_change_passes(repo):
    edit(repo, "app.py", "return a + b", "return b + a")
    result = guard(repo)
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout


@pytest.mark.parametrize(
    ("change", "rule"),
    [
        (("app.py", "return a + b", "return a + b  # noqa: E501"), "silenced-checker"),
        (("app.py", "return a + b", "return a + b  # type: ignore"), "silenced-checker"),
        (("app.py", "return a + b", "return a + b  # pragma: no cover"), "silenced-checker"),
        (("app.py", "return a + b", "raise NotImplementedError"), "unfinished-work"),
        (("app.py", "return a + b", "return a + b  # TODO handle overflow"), "unfinished-work"),
        (
            ("test_app.py", "def test_total", "@pytest.mark.skip\ndef test_total"),
            "test-made-easier",
        ),
        (("test_app.py", "    assert add(0, 0) == 0\n", ""), "assertion-removed"),
    ],
)
def test_lowering_the_bar_fails(repo, change, rule):
    edit(repo, *change)
    result = guard(repo)
    assert result.returncode == 1
    assert f"[{rule}]" in result.stderr


def test_swallowed_exception_fails(repo):
    (repo / "app.py").write_text(
        "def add(a, b):\n    try:\n        return a + b\n    except Exception: pass\n"
    )
    assert guard(repo).returncode == 1


def test_deleted_test_file_fails(repo):
    (repo / "test_app.py").unlink()
    result = guard(repo)
    assert result.returncode == 1
    assert "[test-deleted]" in result.stderr


def test_new_untracked_file_is_checked(repo):
    (repo / "new_module.py").write_text("x = 1  # noqa\n")
    assert guard(repo).returncode == 1


@pytest.mark.parametrize(
    ("old", "new", "rule"),
    [
        ("must not fall below 97.5%", "must not fall below 90%", "threshold-loosened"),
        ("p95 at most 200 ms", "p95 at most 500 ms", "threshold-loosened"),
        ("| Latency | p95 at most 200 ms | bench |\n", "", "rule-removed"),
    ],
)
def test_weakening_constraints_fails(repo, old, new, rule):
    edit(repo, "CONSTRAINTS.md", old, new)
    result = guard(repo)
    assert result.returncode == 1
    assert f"[{rule}]" in result.stderr


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("must not fall below 97.5%", "must not fall below 98%"),
        ("p95 at most 200 ms", "p95 at most 150 ms"),
    ],
)
def test_tightening_constraints_is_silent(repo, old, new):
    edit(repo, "CONSTRAINTS.md", old, new)
    assert guard(repo).returncode == 0


def _exception_row(owner, expires):
    return f"| W1 | silenced-checker | legacy.py | vendored code | {owner} | {expires} |\n"


def test_complete_exception_is_reported_but_passes(repo):
    expires = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    with (repo / "CONSTRAINTS.md").open("a") as f:
        f.write(_exception_row("owner", expires))
    result = guard(repo)
    assert result.returncode == 0
    assert "REVIEW new exception" in result.stderr


@pytest.mark.parametrize(
    ("owner", "days"),
    [("", 30), ("owner", 400), ("owner", -1)],
    ids=["no-owner", "expiry-too-far", "already-expired"],
)
def test_incomplete_exception_fails(repo, owner, days):
    expires = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    with (repo / "CONSTRAINTS.md").open("a") as f:
        f.write(_exception_row(owner, expires))
    assert guard(repo).returncode == 1


def test_constraintsignore_exempts_a_path(repo):
    (repo / ".constraintsignore").write_text("legacy.py\n")
    (repo / "legacy.py").write_text("x = 1  # noqa\n")
    assert guard(repo).returncode == 0


def test_unknown_base_exits_2_not_0(repo):
    result = guard(repo, base="no-such-ref")
    assert result.returncode == 2


def test_outside_a_git_repo_exits_2(tmp_path):
    result = run([sys.executable, str(GUARD)], tmp_path)
    assert result.returncode == 2


def test_docs_that_describe_the_patterns_are_not_flagged(repo):
    (repo / "NOTES.md").write_text("Never add `# noqa` or a TODO; see `pytest.skip`.\n")
    assert guard(repo).returncode == 0


def test_the_same_text_in_code_is_flagged(repo):
    (repo / "notes.py").write_text("x = 1  # noqa\n")
    assert guard(repo).returncode == 1
