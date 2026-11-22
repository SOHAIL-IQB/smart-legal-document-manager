"""Unit tests for the structured diff engine (Phase 4, B10). Pure functions, no database."""

import pytest

from app.utils.diff import diff_documents, has_meaningful_changes, tokenize


def rows_of(type_, result):
    return [row for row in result.rows if row.type == type_]


def side_text(segments):
    return "".join(segment.text for segment in segments)


# --- tokenizer ---------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    ["The tenant shall pay $1,200.00 monthly.", "  indented\ttabs  ", "", "naïve café — 7 días"],
)
def test_tokens_rebuild_the_line_exactly(line):
    assert "".join(tokenize(line)) == line


def test_tokenizer_splits_words_spaces_and_punctuation():
    assert tokenize("pay $1,200.") == ["pay", " ", "$", "1", ",", "200", "."]


# --- line alignment --------------------------------------------------------------


def test_identical_documents_have_only_equal_rows_and_zero_stats():
    result = diff_documents("A\nB", "A\nB")
    assert [row.type for row in result.rows] == ["equal", "equal"]
    assert result.stats.model_dump() == {
        "lines_added": 0,
        "lines_removed": 0,
        "lines_changed": 0,
        "words_added": 0,
        "words_removed": 0,
    }


def test_added_and_removed_lines_have_line_numbers_on_one_side_only():
    result = diff_documents("Keep\nDrop", "Keep\nNew one\nAnd another")
    deleted_or_replaced = [r for r in result.rows if r.type != "equal"]
    assert [r.type for r in deleted_or_replaced] == ["replace", "insert"]

    insert = rows_of("insert", result)[0]
    assert (insert.old_line, insert.new_line, insert.new_text) == (None, 3, "And another")
    assert result.stats.lines_added == 1
    assert result.stats.lines_changed == 1


def test_pure_deletion():
    result = diff_documents("A\nB\nC", "A\nC")
    [deleted] = rows_of("delete", result)
    assert (deleted.old_line, deleted.new_line, deleted.old_text) == (2, None, "B")
    assert result.stats.lines_removed == 1
    assert result.stats.words_removed == 1


def test_line_numbers_stay_aligned_after_changes():
    result = diff_documents("1\n2\n3\n4", "0\n1\n2\n4")
    equal = rows_of("equal", result)
    assert [(r.old_line, r.new_line) for r in equal] == [(1, 2), (2, 3), (4, 4)]


def test_repeated_blank_lines_do_not_confuse_alignment():
    # difflib's autojunk heuristic would treat frequent lines as junk on long inputs.
    old = "\n".join(["Clause", ""] * 150)  # ends with a newline
    new = old + "New final clause"
    result = diff_documents(old, new)
    changed = [r for r in result.rows if r.type != "equal"]
    assert [(r.type, r.new_text) for r in changed] == [("insert", "New final clause")]


def test_frequently_repeated_lines_still_align_to_a_one_line_change():
    # 400 lines cycling through 20 headings: difflib's autojunk marks every heading as junk and
    # reports ~200 changed lines. Long contracts repeat headings and signature lines like this.
    old_lines = [f"Section {i % 20} heading" for i in range(400)]
    new_lines = list(old_lines)
    new_lines[200] = "Section 0 heading, amended"
    result = diff_documents("\n".join(old_lines), "\n".join(new_lines))
    changed = [r for r in result.rows if r.type != "equal"]
    assert [(r.type, r.new_line) for r in changed] == [("replace", 201)]


def test_windows_line_endings_are_treated_like_unix():
    assert all(r.type == "equal" for r in diff_documents("A\r\nB", "A\nB").rows)


# --- word level ------------------------------------------------------------------------


def test_changed_line_gets_word_segments_that_rebuild_each_side():
    old = "This contract is valid for 1 year."
    new = "This contract is valid for 2 years."
    [row] = diff_documents(old, new).rows

    assert row.type == "replace"
    assert side_text(row.old_segments) == old
    assert side_text(row.new_segments) == new
    assert [s.text for s in row.old_segments if s.op == "delete"] == ["1 year"]
    assert [s.text for s in row.new_segments if s.op == "insert"] == ["2 years"]


def test_adjacent_segments_with_the_same_op_are_merged():
    [row] = diff_documents("a b c", "x y c").rows
    ops = [s.op for s in row.new_segments]
    assert ops == ["insert", "equal"]  # "x y" is one insert, " c" one equal


def test_word_stats_count_words_not_spaces_or_punctuation():
    result = diff_documents("Pay 100 dollars.", "Pay 250 euros, monthly.")
    assert result.stats.words_removed == 2  # 100, dollars
    assert result.stats.words_added == 3  # 250, euros, monthly


def test_whitespace_only_change_is_flagged():
    [row] = diff_documents("Clause  A", "Clause A").rows
    assert row.type == "replace"
    assert row.whitespace_only is True


def test_wording_change_is_not_whitespace_only():
    [row] = diff_documents("Clause A", "Clause B").rows
    assert row.whitespace_only is False


def test_unicode_words():
    [row] = diff_documents("Le café est fermé", "Le café est ouvert").rows
    assert [s.text for s in row.new_segments if s.op == "insert"] == ["ouvert"]


# --- context collapsing -----------------------------------------------------------------------


def test_context_collapses_long_unchanged_runs():
    old = "\n".join(f"line {i}" for i in range(1, 21))
    new = old.replace("line 10", "line ten")
    result = diff_documents(old, new, context=2)

    types = [r.type for r in result.rows]
    assert types == ["skip", "equal", "equal", "replace", "equal", "equal", "skip"]
    # 9 unchanged lines before the change keep 2 after them; 10 after keep 2 before them.
    assert [r.skipped for r in result.rows if r.type == "skip"] == [7, 8]


def test_context_keeps_short_runs():
    result = diff_documents("a\nb\nc", "a\nB\nc", context=3)
    assert [r.type for r in result.rows] == ["equal", "replace", "equal"]


def test_context_on_identical_documents_collapses_everything():
    result = diff_documents("a\nb\nc\nd", "a\nb\nc\nd", context=1)
    assert [(r.type, r.skipped) for r in result.rows] == [("skip", 4)]


# --- meaningful-change detection (existing behaviour, kept) --------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "meaningful"),
    [
        ("A\nB", "A \nB", False),
        ("A\n\nB", "A\nB", False),
        ("A  B", "A B", False),
        ("A B", "A C", True),
        ("A", "A\nB", True),
    ],
)
def test_has_meaningful_changes(old, new, meaningful):
    assert has_meaningful_changes(old, new) is meaningful


# --- invariants over random inputs ---------------------------------------------------------------


def _random_doc(rng, vocabulary):
    lines = []
    for _ in range(rng.randint(0, 12)):
        words = [rng.choice(vocabulary) for _ in range(rng.randint(0, 6))]
        lines.append(rng.choice([" ", "  ", "\t"]).join(words))
    return "\n".join(lines)


def _mutate(rng, doc, vocabulary):
    lines = doc.splitlines()
    for _ in range(rng.randint(0, 4)):
        action = rng.choice(["insert", "delete", "edit"])
        if action == "insert" or not lines:
            lines.insert(rng.randint(0, len(lines)), rng.choice(vocabulary))
        elif action == "delete":
            lines.pop(rng.randrange(len(lines)))
        else:
            k = rng.randrange(len(lines))
            words = lines[k].split() or [""]
            words[rng.randrange(len(words))] = rng.choice(vocabulary)
            lines[k] = " ".join(words)
    return "\n".join(lines)


def test_rows_and_segments_reconstruct_both_documents_for_random_inputs():
    import random

    rng = random.Random(20261122)  # fixed seed: deterministic
    vocabulary = ["the", "Tenant", "shall", "pay", "$1,200", "rent.", "§4(b)", "café", "", "—"]
    for _ in range(300):
        old = _random_doc(rng, vocabulary)
        new = _mutate(rng, old, vocabulary)
        result = diff_documents(old, new)

        old_rows = [r.old_text for r in result.rows if r.old_line is not None]
        new_rows = [r.new_text for r in result.rows if r.new_line is not None]
        assert old_rows == old.splitlines()
        assert new_rows == new.splitlines()
        assert [r.old_line for r in result.rows if r.old_line] == list(range(1, len(old_rows) + 1))
        assert [r.new_line for r in result.rows if r.new_line] == list(range(1, len(new_rows) + 1))

        for row in result.rows:
            if row.type == "replace":
                assert side_text(row.old_segments) == row.old_text
                assert side_text(row.new_segments) == row.new_text
                assert all(s.op != "insert" for s in row.old_segments)
                assert all(s.op != "delete" for s in row.new_segments)

        counts = {t: len(rows_of(t, result)) for t in ("insert", "delete", "replace")}
        assert result.stats.lines_added == counts["insert"]
        assert result.stats.lines_removed == counts["delete"]
        assert result.stats.lines_changed == counts["replace"]
        if old == new:
            assert counts == {"insert": 0, "delete": 0, "replace": 0}
