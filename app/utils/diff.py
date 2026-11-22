"""Text comparison for legal documents.

`diff_documents` produces side-by-side rows: lines are aligned first, then each changed line
is compared word by word so the UI can highlight exactly which words changed.
"""

import difflib
import re
from typing import Literal

from pydantic import BaseModel

# Words (letters/digits, any script), runs of whitespace, or single punctuation characters.
# Joining the tokens always reproduces the original line exactly.
_TOKEN = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)
_WORD = re.compile(r"\w", re.UNICODE)

RowType = Literal["equal", "insert", "delete", "replace", "skip"]
SegmentOp = Literal["equal", "insert", "delete"]


class Segment(BaseModel):
    op: SegmentOp
    text: str


class DiffRow(BaseModel):
    type: RowType
    old_line: int | None = None  # 1-based line number in the older version
    new_line: int | None = None
    old_text: str | None = None
    new_text: str | None = None
    old_segments: list[Segment] | None = None  # only for "replace"
    new_segments: list[Segment] | None = None
    whitespace_only: bool = False  # "replace" rows that differ only in spacing
    skipped: int | None = None  # only for "skip": how many unchanged lines were collapsed


class DiffStats(BaseModel):
    lines_added: int = 0
    lines_removed: int = 0
    lines_changed: int = 0
    words_added: int = 0
    words_removed: int = 0


class DocumentDiff(BaseModel):
    rows: list[DiffRow]
    stats: DiffStats


def tokenize(line: str) -> list[str]:
    return _TOKEN.findall(line)


def _count_words(text: str) -> int:
    return sum(1 for token in tokenize(text) if _WORD.match(token))


def _merge(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        if not segment.text:
            continue
        if merged and merged[-1].op == segment.op:
            merged[-1] = Segment(op=segment.op, text=merged[-1].text + segment.text)
        else:
            merged.append(segment)
    return merged


def _word_diff(old: str, new: str) -> tuple[list[Segment], list[Segment]]:
    a, b = tokenize(old), tokenize(new)
    opcodes = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    old_side: list[Segment] = []
    new_side: list[Segment] = []
    for index, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        old_text, new_text = "".join(a[i1:i2]), "".join(b[j1:j2])
        # A lone space matched between two changes ("1 year" -> "2 years") reads better as part
        # of one change than as three fragments, so it is absorbed into the change.
        between_changes = 0 < index < len(opcodes) - 1 and not old_text.strip()
        if tag == "equal" and not between_changes:
            old_side.append(Segment(op="equal", text=old_text))
            new_side.append(Segment(op="equal", text=new_text))
        else:
            old_side.append(Segment(op="delete", text=old_text))
            new_side.append(Segment(op="insert", text=new_text))
    return _merge(old_side), _merge(new_side)


def _collapse(rows: list[DiffRow], context: int) -> list[DiffRow]:
    """Replace unchanged runs longer than 2*context with a single "skip" row."""
    result: list[DiffRow] = []
    i = 0
    while i < len(rows):
        if rows[i].type != "equal":
            result.append(rows[i])
            i += 1
            continue
        j = i
        while j < len(rows) and rows[j].type == "equal":
            j += 1
        run = rows[i:j]
        keep_before = context if i > 0 else 0  # context after a preceding change
        keep_after = context if j < len(rows) else 0  # context before a following change
        if len(run) > keep_before + keep_after:
            result.extend(run[:keep_before])
            result.append(DiffRow(type="skip", skipped=len(run) - keep_before - keep_after))
            result.extend(run[len(run) - keep_after :] if keep_after else [])
        else:
            result.extend(run)
        i = j
    return result


def diff_documents(old_text: str, new_text: str, *, context: int | None = None) -> DocumentDiff:
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    rows: list[DiffRow] = []
    stats = DiffStats()

    def deleted(index: int) -> DiffRow:
        stats.lines_removed += 1
        stats.words_removed += _count_words(old_lines[index])
        return DiffRow(type="delete", old_line=index + 1, old_text=old_lines[index])

    def inserted(index: int) -> DiffRow:
        stats.lines_added += 1
        stats.words_added += _count_words(new_lines[index])
        return DiffRow(type="insert", new_line=index + 1, new_text=new_lines[index])

    # autojunk=False: the heuristic misaligns documents with many repeated (e.g. blank) lines.
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rows.extend(
                DiffRow(
                    type="equal",
                    old_line=i + 1,
                    new_line=j + 1,
                    old_text=old_lines[i],
                    new_text=new_lines[j],
                )
                for i, j in zip(range(i1, i2), range(j1, j2), strict=True)
            )
        elif tag == "delete":
            rows.extend(deleted(i) for i in range(i1, i2))
        elif tag == "insert":
            rows.extend(inserted(j) for j in range(j1, j2))
        else:  # replace: pair lines up; leftovers on either side are pure deletes/inserts
            paired = min(i2 - i1, j2 - j1)
            for k in range(paired):
                old_line, new_line = old_lines[i1 + k], new_lines[j1 + k]
                old_segments, new_segments = _word_diff(old_line, new_line)
                stats.lines_changed += 1
                stats.words_removed += sum(
                    _count_words(s.text) for s in old_segments if s.op == "delete"
                )
                stats.words_added += sum(
                    _count_words(s.text) for s in new_segments if s.op == "insert"
                )
                rows.append(
                    DiffRow(
                        type="replace",
                        old_line=i1 + k + 1,
                        new_line=j1 + k + 1,
                        old_text=old_line,
                        new_text=new_line,
                        old_segments=old_segments,
                        new_segments=new_segments,
                        whitespace_only=old_line.split() == new_line.split(),
                    )
                )
            rows.extend(deleted(i) for i in range(i1 + paired, i2))
            rows.extend(inserted(j) for j in range(j1 + paired, j2))

    if context is not None:
        rows = _collapse(rows, context)
    return DocumentDiff(rows=rows, stats=stats)


def build_unified_diff(old_text: str, new_text: str) -> list[str]:
    return list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="Before",
            tofile="After",
            lineterm="",
        )
    )


def normalize_for_meaningful_change(content: str) -> str:
    normalized_lines = [" ".join(line.split()) for line in content.splitlines()]
    return "\n".join(line for line in normalized_lines if line)


def has_meaningful_changes(old_text: str, new_text: str) -> bool:
    return normalize_for_meaningful_change(old_text) != normalize_for_meaningful_change(new_text)
