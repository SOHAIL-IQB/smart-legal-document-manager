"""The parse worker's own logic, tested in this process (Phase 7 T6).

tests/test_parse_limits.py drives the worker across the real process boundary, which coverage
can't see: the worker may not write files and leaves with os._exit. These tests call the same
functions directly so their branches are measured. Nothing here applies limits to the test run:
setrlimit and the OOM-score file are replaced with recorders.
"""

import io
import json
import resource
import sys
import zipfile

import pytest

from app.utils import parse_worker
from app.utils.parse_worker import RefusedError, docx_text, normalize_text, pdf_text
from tests.files import (
    make_blank_pdf,
    make_docx,
    make_encrypted_pdf,
    make_pdf,
    make_zip_bomb_docx,
)


def refusal(call, *args):
    with pytest.raises(RefusedError) as caught:
        call(*args)
    return caught.value.reason


def test_normalize_text_unifies_newlines_and_collapses_blank_runs():
    assert normalize_text("  a\r\nb\rc\x00  \n\n\n\nd  \n") == "a\nb\nc\n\nd"


def test_pdf_text_returns_the_text_and_page_count():
    text, pages = pdf_text(make_pdf("First page.", "Second page."))
    assert pages == 2
    assert "First page." in text and "Second page." in text


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (make_encrypted_pdf(), "encrypted"),
        (make_blank_pdf(), "no_text"),
        (b"%PDF-1.4 this is not really a pdf", "damaged"),
    ],
)
def test_pdf_refusals(data, reason):
    assert refusal(pdf_text, data) == reason


def test_pdf_page_limit(monkeypatch):
    monkeypatch.setattr(parse_worker, "MAX_PDF_PAGES", 1)
    assert refusal(pdf_text, make_pdf("one", "two")) == "too_many_pages"


def test_docx_text_keeps_paragraphs_and_tables_in_order():
    data = make_docx("Heading", "Body text.", table=[["Party", "Role"], ["Asha", "Owner"]])
    assert docx_text(data) == "Heading\nBody text.\nParty | Role\nAsha | Owner"


def test_docx_refusals():
    assert refusal(docx_text, b"PK\x03\x04 broken zip") == "damaged"
    assert refusal(docx_text, make_zip_bomb_docx(uncompressed_mb=60)) == "too_large_uncompressed"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:  # a valid zip that isn't a Word document
        archive.writestr("hello.txt", "hi")
    assert refusal(docx_text, out.getvalue()) == "damaged"


def test_limit_resources_sets_every_limit_and_tolerates_unsupported_ones(monkeypatch):
    calls = []

    def record(limit, values):
        calls.append((limit, values))
        if limit == resource.RLIMIT_AS:
            raise ValueError("not supported here")  # e.g. macOS: the rest still apply

    oom_writes = []

    class OomFile(io.StringIO):
        def close(self):
            oom_writes.append(self.getvalue())
            super().close()

    monkeypatch.setattr(resource, "setrlimit", record)
    monkeypatch.setattr(parse_worker, "open", lambda *_a, **_k: OomFile(), raising=False)
    parse_worker.limit_resources(7, 1024)

    applied = dict(calls)
    assert applied[resource.RLIMIT_CPU] == (7, 7)
    assert applied[resource.RLIMIT_AS] == (1024, 1024)
    assert applied[resource.RLIMIT_FSIZE] == (0, 0)
    assert applied[resource.RLIMIT_CORE] == (0, 0)
    assert applied[resource.RLIMIT_NOFILE] == (64, 64)
    assert applied[resource.RLIMIT_NPROC] == (0, 0)
    assert oom_writes == ["1000"]


def test_limit_resources_can_allow_forking_and_skips_a_missing_oom_file(monkeypatch):
    calls = []

    def no_proc(*_args, **_kwargs):
        raise OSError("no /proc here")

    monkeypatch.setattr(resource, "setrlimit", lambda limit, values: calls.append(limit))
    monkeypatch.setattr(parse_worker, "open", no_proc, raising=False)
    parse_worker.limit_resources(7, 1024, allow_fork=True)
    assert resource.RLIMIT_NPROC not in calls
    assert resource.RLIMIT_CPU in calls


class _ExitCalledError(Exception):
    pass


def run_main(monkeypatch, kind, data):
    stdout = io.BytesIO()
    monkeypatch.setattr(sys, "argv", ["parse_worker", kind, "5", "1024"])
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data)))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(stdout))
    monkeypatch.setattr(parse_worker, "limit_resources", lambda *_a, **_k: None)

    def exit_(code):
        raise _ExitCalledError(code)

    monkeypatch.setattr(parse_worker.os, "_exit", exit_)
    with pytest.raises(_ExitCalledError) as exited:
        parse_worker.main()
    assert exited.value.args == (0,)
    header_line, _, body = stdout.getvalue().partition(b"\n")
    header = json.loads(header_line)
    assert header["length"] == len(body)
    return header, body


def test_main_replies_with_header_and_text(monkeypatch):
    header, body = run_main(monkeypatch, "pdf", make_pdf("Clause one."))
    assert header == {"status": "ok", "pages": 1, "length": len(body)}
    assert body == b"Clause one."


def test_main_replies_for_docx_without_a_page_count(monkeypatch):
    header, body = run_main(monkeypatch, "docx", make_docx("Recital."))
    assert (header["status"], header["pages"], body) == ("ok", None, b"Recital.")


def test_main_refuses_an_unknown_kind(monkeypatch):
    header, body = run_main(monkeypatch, "exe", b"MZ")
    assert (header, body) == ({"status": "refused", "reason": "damaged", "length": 0}, b"")


def test_main_refuses_text_over_the_reply_cap(monkeypatch):
    monkeypatch.setattr(parse_worker, "MAX_REPLY_BYTES", 5)
    header, _ = run_main(monkeypatch, "pdf", make_pdf("More than five bytes."))
    assert header == {"status": "refused", "reason": "too_long", "length": 0}


def test_every_reason_the_worker_sends_has_a_message_on_the_server():
    from app.utils.extract import _MESSAGES

    assert set(_MESSAGES) == parse_worker.REASONS
