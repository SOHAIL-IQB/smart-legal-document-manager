#!/usr/bin/env python3
"""Floor guard: diff-scoped enforcement of the CONSTRAINTS.md floor.

Python port of the constraint-driven-development reference implementation; the contract is
unchanged:
- Input: the diff between the merge base and the working tree, plus untracked files.
- Detects the moves that lower the bar: a new suppression comment, a test made easier (skip/xfail
  added, test file deleted, assertion removed), unfinished work (stub, swallowed exception, TODO),
  a CONSTRAINTS.md rule weakened or removed, and a new Exceptions row.
- Exit codes: 0 clean, 1 at least one violation, 2 the guard could not run. 2 never reads as 0.
- Reports the rule and location only; tightening the bar is silent, loosening it is loud.

One deliberate deviation from the reference: a new Exceptions row is *reported* but only blocks
when it lacks an owner or an expiry date within 90 days. With direct pushes to main, a blocking
row would make the documented escape hatch unusable.

Usage: python scripts/floor_guard.py [--base <ref>]   (default base: origin/main)

A deliberate exception is a row in CONSTRAINTS.md's Exceptions table (which this guard reports
when added, so it shows up in review) plus a path glob in `.constraintsignore`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class GuardError(Exception):
    """The guard could not run. Exit code 2, never treated as clean."""


def git(*args: str, diff_exit: bool = False) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    # `git diff --no-index` exits 1 whenever the sides differ, which is normal for a new file.
    if result.returncode == 0 or (diff_exit and result.returncode == 1):
        return result.stdout
    raise GuardError(f"git {' '.join(args)} failed: {result.stderr.strip()}")


@dataclass(frozen=True)
class Line:
    file: str
    text: str


def collect_diff(base: str) -> tuple[list[Line], list[Line], list[str]]:
    top = git("rev-parse", "--show-toplevel").strip()
    if not top:
        raise GuardError("not inside a git work tree")
    os.chdir(top)
    merge_base = git("merge-base", base, "HEAD").strip()
    if not merge_base:
        raise GuardError(f"no merge base against {base}")

    diff = git("diff", "--unified=0", merge_base, "--")
    for name in filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()):
        diff += "\n" + git("diff", "--no-index", "--unified=0", "/dev/null", name, diff_exit=True)

    added: list[Line] = []
    removed: list[Line] = []
    deleted: list[str] = []
    file = old_file = ""
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff "):
            in_header = True
        elif line.startswith("@@"):
            in_header = False
        elif in_header:
            if line.startswith("--- "):
                old_file = re.sub(r"^[ab]/", "", line[4:])
            elif line.startswith("+++ "):
                new_file = re.sub(r"^[ab]/", "", line[4:])
                file = old_file if new_file == "/dev/null" else new_file
                if new_file == "/dev/null":
                    deleted.append(file)
        elif line.startswith("+"):
            added.append(Line(file, line[1:]))
        elif line.startswith("-"):
            removed.append(Line(file, line[1:]))
    return added, removed, deleted


# 1. Silenced checker.
SUPPRESSIONS = re.compile(
    r"#\s*noqa|#\s*type:\s*ignore|pragma:\s*no\s*cover|#\s*nosec|nosemgrep|gitleaks:allow"
    r"|ruff:\s*noqa|pylint:\s*disable|@ts-ignore|eslint-disable"
)
# 4. Unfinished work.
STUBS = re.compile(r"raise\s+NotImplementedError|except[^:\n]*:\s*pass\b|\bTODO\b|\bFIXME\b")
# 2. A test made easier.
SKIPS = re.compile(
    r"@pytest\.mark\.(skip|xfail)\b|pytest\.(skip|xfail)\(|@unittest\.skip|\.skip\(|\bxit\("
)
ASSERTION = re.compile(r"\bassert\b|pytest\.raises|\bexpect\(")
EXCEPTION_ROW = re.compile(r"^\|\s*(W|E)\d+\s*\|")

MIN_BEFORE = re.compile(
    r"(>=|>|≥|at least|minimum|\bmin\b|no less than|not fall below|not fall|not drop)\s*$"
)
MAX_BEFORE = re.compile(
    r"(<=|<|≤|at most|maximum|\bmax\b|no more than|under|below|not grow|not exceed)\s*$"
)
MIN_AFTER = re.compile(r"^\s*\S*\s*(?:\|\s*)?(or more|or higher|must not fall|must not drop)")
MAX_AFTER = re.compile(r"^\s*\S*\s*(?:\|\s*)?(or less|or lower|must not grow|must not exceed)")


# Suppression, stub and skip patterns only mean something in source files; docs that *describe*
# them (CONSTRAINTS.md, specs) would otherwise be false positives. Known gap: a rule silenced
# through pyproject.toml's ruff ignore lists is not detected.
CODE_SUFFIXES = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def is_code(path: str) -> bool:
    return path.endswith(CODE_SUFFIXES)


def is_test(path: str) -> bool:
    return bool(re.search(r"(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$", path))


def is_constraints(path: str) -> bool:
    return path.endswith("CONSTRAINTS.md")


def rule_key(text: str) -> str | None:
    s = text.strip()
    if s.startswith("|"):
        cells = [c.strip() for c in s.split("|") if c.strip()]
        return cells[0] if cells else ""
    if re.match(r"^[-*] ", s):
        return s[2:].split(":")[0].strip()
    return None  # prose, headings, dates: not a rule


def thresholds(text: str) -> list[tuple[float, str | None]]:
    out = []
    for match in re.finditer(r"\d+(?:\.\d+)?", text):
        before = text[max(0, match.start() - 24) : match.start()].lower()
        after = text[match.end() : match.end() + 40].lower()
        if MIN_BEFORE.search(before) or MIN_AFTER.search(after):
            direction: str | None = "min"
        elif MAX_BEFORE.search(before) or MAX_AFTER.search(after):
            direction = "max"
        else:
            direction = None
        out.append((float(match.group()), direction))
    return out


def ignored_globs() -> list[str]:
    path = Path(".constraintsignore")
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    return [g.strip() for g in lines if g.strip() and not g.startswith("#")]


MAX_EXCEPTION_DAYS = 90


def exception_row_is_complete(text: str, today: dt.date | None = None) -> bool:
    """| ID | Rule | Path | Reason | Owner | Expires |  -- owner set, expiry within 90 days."""
    cells = [c.strip() for c in text.strip().strip("|").split("|")]
    if len(cells) < 6 or not cells[4]:
        return False
    try:
        expires = dt.date.fromisoformat(cells[5])
    except ValueError:
        return False
    today = today or dt.date.today()
    return today <= expires <= today + dt.timedelta(days=MAX_EXCEPTION_DAYS)


def find_violations(
    added: list[Line],
    removed: list[Line],
    deleted: list[str],
    ignore: list[str],
    notices: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    notices = notices if notices is not None else []

    def flag(rule: str, file: str, text: str) -> None:
        if not any(fnmatch.fnmatch(file, g) for g in ignore):
            findings.append((rule, file, text.strip()[:120]))

    for line in added:
        if is_code(line.file):
            if SUPPRESSIONS.search(line.text):
                flag("silenced-checker", line.file, line.text)
            if STUBS.search(line.text):
                flag("unfinished-work", line.file, line.text)
            if SKIPS.search(line.text):
                flag("test-made-easier", line.file, line.text)
        if is_constraints(line.file) and EXCEPTION_ROW.match(line.text.strip()):
            notices.append(line.text.strip()[:120])
            if not exception_row_is_complete(line.text):
                flag("exception-without-owner-or-expiry", line.file, line.text)

    for path in deleted:
        if is_test(path):
            flag("test-deleted", path, "file deleted")
    for line in removed:
        if is_test(line.file) and line.file not in deleted and ASSERTION.search(line.text):
            flag("assertion-removed", line.file, line.text)

    removed_rules = [r for r in removed if is_constraints(r.file) and rule_key(r.text) is not None]
    added_rules = [a for a in added if is_constraints(a.file) and rule_key(a.text) is not None]
    for old in removed_rules:
        new = next((a for a in added_rules if rule_key(a.text) == rule_key(old.text)), None)
        if new is None:
            if not EXCEPTION_ROW.match(old.text.strip()):  # dropping an exception tightens
                flag("rule-removed", old.file, old.text)
            continue
        was, now = thresholds(old.text), thresholds(new.text)
        verdict = None
        for direction in ("min", "max", None):
            before = [n for n, d in was if d == direction]
            after = [n for n, d in now if d == direction]
            for i, value in enumerate(before):
                if verdict:
                    break
                if i >= len(after):
                    verdict = "threshold-removed"
                elif after[i] == value:
                    continue
                elif direction is None:
                    verdict = "threshold-changed"
                elif (direction == "min" and after[i] < value) or (
                    direction == "max" and after[i] > value
                ):
                    verdict = "threshold-loosened"
        if verdict:
            flag(verdict, old.file, f"{old.text.strip()}  ->  {new.text.strip()}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()
    try:
        added, removed, deleted = collect_diff(args.base)
    except GuardError as exc:
        print(f"floor-guard: {exc}", file=sys.stderr)
        return 2

    notices: list[str] = []
    findings = find_violations(added, removed, deleted, ignored_globs(), notices)
    for row in notices:
        print(f"floor-guard: REVIEW new exception: {row}", file=sys.stderr)
    if not findings:
        print("floor-guard: clean")
        return 0
    print(f"floor-guard: {len(findings)} floor violation(s):", file=sys.stderr)
    for rule, file, text in findings:
        print(f"  [{rule}] {file}: {text}", file=sys.stderr)
    print(
        "\nEach is a move that lowers the bar. Fix the code, or record a tracked exception "
        "(Exceptions row in CONSTRAINTS.md + path in .constraintsignore).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
