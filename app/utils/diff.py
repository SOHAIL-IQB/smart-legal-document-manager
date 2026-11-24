"""Text comparison for legal documents.

`diff_documents` produces side-by-side rows: lines are aligned first, then each changed line
is compared word by word so the UI can highlight exactly which words changed.
"""

import bisect
import difflib
import re
from collections import Counter
from collections.abc import Hashable, Sequence
from typing import Literal

from pydantic import BaseModel

# Words (letters/digits, any script), runs of whitespace, or single punctuation characters.
# Joining the tokens always reproduces the original line exactly.
_TOKEN = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)
_WORD = re.compile(r"\w", re.UNICODE)

RowType = Literal["equal", "insert", "delete", "replace", "skip"]
SegmentOp = Literal["equal", "insert", "delete"]
Opcode = tuple[str, int, int, int, int]

# Matching work allowed for one comparison (review finding H1), in SequenceMatcher cells: a
# region of n old and m new elements is charged n * m. With autojunk off, difflib's time grows
# faster than that for repetitive regions with dense edits (its recursion rescans), so the value
# was set by the worst pattern measured: 0.30 s at 250,000 cells (LOG.md 017). Typical documents
# use a tiny fraction of it, because unique lines anchor the alignment first.
MAX_COMPARE_CELLS = 250_000


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
    changes: list[str]  # unified diff lines (difflib's format), from the same line alignment
    approximate: bool = False  # True when part of the comparison ran out of budget


class _Budget:
    def __init__(self, cells: int) -> None:
        self.left = cells
        self.exhausted = False

    def spend(self, cells: int) -> bool:
        if cells > self.left:
            self.exhausted = True
            return False
        self.left -= cells
        return True


def _unique_anchors(a: Sequence[Hashable], b: Sequence[Hashable]) -> list[tuple[int, int]]:
    """Positions (i, j) of elements that occur exactly once in `a` and once in `b`, keeping the
    longest chain that is in order on both sides (the idea behind patience diff).

    Real documents are mostly unique paragraphs, so the anchors split a long comparison into
    many small gaps. Linear in the input, plus k log k for k shared unique elements.
    """
    count_a, count_b = Counter(a), Counter(b)
    where_in_b = {value: j for j, value in enumerate(b) if count_b[value] == 1}
    pairs = [
        (i, where_in_b[value])
        for i, value in enumerate(a)
        if count_a[value] == 1 and value in where_in_b
    ]
    # Longest increasing subsequence of j (pairs are already ordered by i).
    tails: list[int] = []  # tails[k]: index into pairs of the best chain of length k + 1
    tail_js: list[int] = []  # the j of each tail, kept sorted for bisect
    previous: list[int] = [-1] * len(pairs)
    for index, (_, j) in enumerate(pairs):
        k = bisect.bisect_left(tail_js, j)
        if k:
            previous[index] = tails[k - 1]
        if k == len(tails):
            tails.append(index)
            tail_js.append(j)
        else:
            tails[k] = index
            tail_js[k] = j
    chain: list[tuple[int, int]] = []
    index = tails[-1] if tails else -1
    while index != -1:
        chain.append(pairs[index])
        index = previous[index]
    return chain[::-1]


def _gap_opcodes(
    a: Sequence[Hashable],
    b: Sequence[Hashable],
    a_range: tuple[int, int],
    b_range: tuple[int, int],
    budget: _Budget,
) -> list[Opcode]:
    """Opcodes for a[alo:ahi] -> b[blo:bhi]: trim the common ends in linear time, then match
    the rest exactly if the budget allows, else report it as one replaced block."""
    (alo, ahi), (blo, bhi) = a_range, b_range
    opcodes: list[Opcode] = []
    head = 0
    while alo + head < ahi and blo + head < bhi and a[alo + head] == b[blo + head]:
        head += 1
    if head:
        opcodes.append(("equal", alo, alo + head, blo, blo + head))
    alo, blo = alo + head, blo + head
    tail = 0
    while alo < ahi - tail and blo < bhi - tail and a[ahi - 1 - tail] == b[bhi - 1 - tail]:
        tail += 1
    ahi, bhi = ahi - tail, bhi - tail

    if alo < ahi and blo < bhi:
        if budget.spend((ahi - alo) * (bhi - blo)):
            matcher = difflib.SequenceMatcher(None, a[alo:ahi], b[blo:bhi], autojunk=False)
            opcodes += [
                (tag, i1 + alo, i2 + alo, j1 + blo, j2 + blo)
                for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            ]
        else:
            opcodes.append(("replace", alo, ahi, blo, bhi))
    elif alo < ahi:
        opcodes.append(("delete", alo, ahi, blo, blo))
    elif blo < bhi:
        opcodes.append(("insert", alo, alo, blo, bhi))
    if tail:
        opcodes.append(("equal", ahi, ahi + tail, bhi, bhi + tail))
    return opcodes


def _opcodes(a: Sequence[Hashable], b: Sequence[Hashable], budget: _Budget) -> list[Opcode]:
    """difflib-style opcodes turning `a` into `b`: exact while the budget lasts.

    Unique shared elements anchor the alignment; each gap between anchors is matched on its own.
    Adjacent equal runs are merged, so the opcodes read like difflib's.
    """
    opcodes: list[Opcode] = []
    i = j = 0
    for anchor_i, anchor_j in _unique_anchors(a, b):
        opcodes += _gap_opcodes(a, b, (i, anchor_i), (j, anchor_j), budget)
        opcodes.append(("equal", anchor_i, anchor_i + 1, anchor_j, anchor_j + 1))
        i, j = anchor_i + 1, anchor_j + 1
    opcodes += _gap_opcodes(a, b, (i, len(a)), (j, len(b)), budget)

    merged: list[Opcode] = []
    for opcode in opcodes:
        if merged and opcode[0] == "equal" == merged[-1][0]:
            _, i1, _, j1, _ = merged[-1]
            merged[-1] = ("equal", i1, opcode[2], j1, opcode[4])
        else:
            merged.append(opcode)
    return merged


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


def _word_diff(old: str, new: str, budget: _Budget) -> tuple[list[Segment], list[Segment]]:
    a, b = tokenize(old), tokenize(new)
    opcodes = _opcodes(a, b, budget)
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


def diff_documents(
    old_text: str,
    new_text: str,
    *,
    context: int | None = None,
    max_cells: int = MAX_COMPARE_CELLS,
) -> DocumentDiff:
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    rows: list[DiffRow] = []
    stats = DiffStats()
    budget = _Budget(max_cells)

    def deleted(index: int) -> DiffRow:
        stats.lines_removed += 1
        stats.words_removed += _count_words(old_lines[index])
        return DiffRow(type="delete", old_line=index + 1, old_text=old_lines[index])

    def inserted(index: int) -> DiffRow:
        stats.lines_added += 1
        stats.words_added += _count_words(new_lines[index])
        return DiffRow(type="insert", new_line=index + 1, new_text=new_lines[index])

    # autojunk stays off: it misaligns documents with frequently repeated lines (headings,
    # signature blocks); unique-line anchors keep long documents fast instead.
    line_opcodes = _opcodes(old_lines, new_lines, budget)
    for tag, i1, i2, j1, j2 in line_opcodes:
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
                old_segments, new_segments = _word_diff(old_line, new_line, budget)
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
    return DocumentDiff(
        rows=rows,
        stats=stats,
        changes=_unified(old_lines, new_lines, line_opcodes),
        approximate=budget.exhausted,
    )


class _KnownOpcodes(difflib.SequenceMatcher):
    """A matcher that reports opcodes already computed, so grouping costs no new matching."""

    def __init__(self, a: list[str], b: list[str], opcodes: list[Opcode]) -> None:
        super().__init__(None, a, b, autojunk=False)
        self._known = opcodes

    def get_opcodes(self) -> list[Opcode]:
        return self._known


def _unified_range(start: int, stop: int) -> str:
    """A hunk range the way difflib.unified_diff writes it ("3", "3,4" or "2,0")."""
    beginning, length = start + 1, stop - start
    if length == 1:
        return str(beginning)
    if not length:
        beginning -= 1
    return f"{beginning},{length}"


def _unified(old_lines: list[str], new_lines: list[str], opcodes: list[Opcode]) -> list[str]:
    """Unified diff lines in difflib's format (`fromfile="Before"`, `tofile="After"`)."""
    lines: list[str] = []
    for group in _KnownOpcodes(old_lines, new_lines, opcodes).get_grouped_opcodes(3):
        if not lines:
            lines += ["--- Before", "+++ After"]
        first, last = group[0], group[-1]
        lines.append(
            f"@@ -{_unified_range(first[1], last[2])} +{_unified_range(first[3], last[4])} @@"
        )
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                lines += [" " + line for line in old_lines[i1:i2]]
                continue
            if tag in ("replace", "delete"):
                lines += ["-" + line for line in old_lines[i1:i2]]
            if tag in ("replace", "insert"):
                lines += ["+" + line for line in new_lines[j1:j2]]
    return lines


def normalize_for_meaningful_change(content: str) -> str:
    normalized_lines = [" ".join(line.split()) for line in content.splitlines()]
    return "\n".join(line for line in normalized_lines if line)


def has_meaningful_changes(old_text: str, new_text: str) -> bool:
    return normalize_for_meaningful_change(old_text) != normalize_for_meaningful_change(new_text)
