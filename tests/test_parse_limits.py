"""Phase 7 T6 (review finding R5): PDF/DOCX parsing runs in a separate worker process.

Revised after the adversarial review (LOG.md 014): a plain subprocess with stdin/stdout instead of
multiprocessing, a scrubbed environment, reason codes instead of messages, a byte cap on output,
one deadline that includes start-up, and a cap on concurrent parsers.
"""

import contextlib
import json
import os
import threading
import time

import pytest

from app.utils import extract
from app.utils.extract import ParserBusyError, UnreadableFileError, run_parser
from tests.files import make_blank_pdf, make_docx, make_encrypted_pdf, make_pdf

STUB = "tests.parse_worker_stub"


def run_stub(mode, *, timeout=30.0, cpu_seconds=30):
    return run_parser(mode, b"input", timeout=timeout, cpu_seconds=cpu_seconds, module=STUB)


def test_slow_worker_is_stopped_at_the_deadline():
    started = time.monotonic()
    with pytest.raises(UnreadableFileError, match="took too long"):
        run_stub("sleep", timeout=1.0)
    assert time.monotonic() - started < 5


def test_cpu_bound_worker_is_stopped_by_the_cpu_limit():
    started = time.monotonic()
    with pytest.raises(UnreadableFileError):
        run_stub("burn", timeout=30, cpu_seconds=1)
    assert time.monotonic() - started < 10  # the CPU limit, not the 30 s deadline, ended it


def test_crashing_worker_becomes_unreadable_quickly():
    started = time.monotonic()
    with pytest.raises(UnreadableFileError, match="could not be read"):
        run_stub("die")
    assert time.monotonic() - started < 10


def test_large_results_are_returned_without_deadlock():
    text, pages = run_stub("big")
    assert (len(text), pages) == (5_000_000, 1)


def test_endless_output_is_cut_off_at_the_cap(monkeypatch):
    monkeypatch.setattr(extract, "MAX_WORKER_OUTPUT_BYTES", 1_000_000)
    # Short deadline: without the cap this fails in seconds as a timeout, not by filling memory.
    with pytest.raises(UnreadableFileError, match="too long to store"):
        run_stub("flood", timeout=3.0)


def test_malformed_reply_is_a_generic_unreadable_file():
    with pytest.raises(UnreadableFileError, match="could not be read"):
        run_stub("garbage")


def test_worker_cannot_choose_the_message_the_user_sees():
    with pytest.raises(UnreadableFileError) as caught:
        run_stub("unknown-code")
    assert "script" not in caught.value.message
    assert "could not be read" in caught.value.message


def test_known_reason_codes_map_to_our_own_messages():
    with pytest.raises(UnreadableFileError, match="no selectable text"):
        run_stub("no-text")


def test_worker_environment_has_no_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/prod")
    text, _ = run_stub("env")
    assert not text.startswith("LEAK"), text
    assert "SECRET_KEY" not in json.loads(text)


def test_too_many_parsers_at_once_answers_busy(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(extract, "_parser_slots", slots)
    slots.acquire()  # another upload is already parsing
    try:
        with pytest.raises(ParserBusyError):
            run_stub("big", timeout=0.5)
    finally:
        slots.release()


def test_no_worker_process_is_left_behind():
    for mode in ("sleep", "die", "garbage", "big"):
        with contextlib.suppress(UnreadableFileError):  # each mode fails differently
            run_stub(mode, timeout=1.0)
    # Raises ChildProcessError when this process has no children at all, running or zombie.
    with pytest.raises(ChildProcessError):
        os.waitpid(-1, os.WNOHANG)


# --- the real worker --------------------------------------------------------------------------


def test_real_pdf_and_docx_parse_through_the_worker():
    pdf = extract.extract_text("a.pdf", make_pdf("Clause one.", "Clause two."))
    docx = extract.extract_text("a.docx", make_docx("Agreement", table=[["A", "B"]]))
    assert (pdf.text, pdf.pages) == ("Clause one.\n\nClause two.", 2)
    assert docx.text == "Agreement\nA | B"


@pytest.mark.parametrize(
    ("data", "message"),
    [(make_blank_pdf(), "no selectable text"), (make_encrypted_pdf(), "password")],
)
def test_real_worker_refusals_keep_their_meaning(data, message):
    with pytest.raises(UnreadableFileError, match=message):
        extract.extract_text("x.pdf", data)


def test_upload_that_times_out_is_a_422(client, alice, monkeypatch):
    monkeypatch.setattr(extract, "PARSE_TIMEOUT_SECONDS", 0.001)  # start-up alone takes longer
    response = client.post(
        "/api/documents/upload",
        files={"file": ("slow.pdf", make_pdf("Rent."), "application/pdf")},
        headers=alice.headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unreadable_file"


def test_busy_upload_is_a_503(client, alice, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(extract, "_parser_slots", slots)
    monkeypatch.setattr(extract, "PARSE_TIMEOUT_SECONDS", 0.3)
    slots.acquire()
    try:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("a.pdf", make_pdf("Rent."), "application/pdf")},
            headers=alice.headers,
        )
    finally:
        slots.release()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "busy"


def test_txt_files_do_not_start_a_worker(monkeypatch):
    def must_not_run(*_args, **_kwargs):
        raise AssertionError("plain text needs no worker")

    monkeypatch.setattr(extract, "run_parser", must_not_run)
    assert extract.extract_text("a.txt", b"Plain clause.").text == "Plain clause."


# --- cycle-2 review fixes (LOG.md 014) ------------------------------------------------------------


def test_waiting_for_a_slot_does_not_eat_the_parse_deadline(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(extract, "_parser_slots", slots)
    slots.acquire()
    threading.Timer(1.0, slots.release).start()  # the other upload finishes after 1 s
    # Slot wait 3 s, parse deadline 2 s: the parse must still get its full 2 s after the wait.
    text, _ = run_parser("cwd", b"", timeout=2.0, cpu_seconds=30, module=STUB, slot_wait=3.0)
    assert text


def test_busy_is_decided_by_the_slot_wait_not_the_parse_timeout(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(extract, "_parser_slots", slots)
    slots.acquire()
    try:
        started = time.monotonic()
        with pytest.raises(ParserBusyError):
            run_parser("big", b"", timeout=30.0, cpu_seconds=30, module=STUB, slot_wait=0.3)
        assert time.monotonic() - started < 2
    finally:
        slots.release()


@pytest.mark.parametrize("mode", ["truncated", "reason-list", "deep-json", "pages-bool"])
def test_malformed_or_incomplete_replies_are_unreadable_not_500(mode):
    with pytest.raises(UnreadableFileError, match="could not be read"):
        run_stub(mode)


def test_a_complete_reply_is_used_even_if_the_worker_is_slow_to_exit():
    started = time.monotonic()
    text, pages = run_stub("slow-exit", timeout=5.0)
    assert (text, pages) == ("complete reply", 1)
    assert time.monotonic() - started < 4  # didn't wait for the 30 s exit


def test_lone_surrogates_do_not_break_the_reply():
    text, _ = run_stub("surrogate")
    assert text.startswith("bad ") and text.endswith(" char")


def test_worker_runs_from_the_filesystem_root():
    text, _ = run_stub("cwd")
    assert os.path.realpath(text) == os.path.realpath("/")


def test_worker_cannot_write_files():
    text, _ = run_stub("write-file")
    assert text == "blocked"


def test_worker_cannot_fork():
    text, _ = run_stub("fork")
    assert text == "blocked"


def test_processes_the_worker_starts_are_killed_with_it():
    # Even where forking is allowed (e.g. a root development shell), the whole process group goes.
    text, _ = run_stub("grandchild-unlimited")
    grandchild = int(text)
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail(f"grandchild {grandchild} is still running")


def test_the_oom_killer_prefers_the_worker():
    text, _ = run_stub("oom")
    expected = "1000" if os.path.exists("/proc/self/oom_score_adj") else "unsupported"
    assert text == expected


def test_server_side_failures_are_busy_not_500(monkeypatch):
    def no_threads(*_args, **_kwargs):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(extract.threading.Thread, "start", no_threads)
    with pytest.raises(ParserBusyError):
        run_stub("big")


def test_float_cpu_seconds_are_accepted():
    text, _ = run_parser("cwd", b"", timeout=10.0, cpu_seconds=20.0, module=STUB)
    assert text


# --- cycle-3 review findings (LOG.md 014) ------------------------------------------------------


def test_a_reply_header_larger_than_any_real_one_is_unreadable():
    with pytest.raises(UnreadableFileError, match="could not be read"):
        run_stub("big-header")


def test_a_reply_already_waiting_at_the_deadline_is_still_used():
    read_end, write_end = os.pipe()
    reply = json.dumps({"status": "ok", "pages": 1, "length": 2}).encode() + b"\nok"
    os.write(write_end, reply)
    os.close(write_end)

    class FinishedWorker:
        stdout = os.fdopen(read_end, "rb")

    with FinishedWorker.stdout:
        assert extract._read_reply(FinishedWorker, time.monotonic() - 1) == reply


def test_the_reply_is_decoded_while_the_parser_slot_is_still_held(monkeypatch):
    slots = threading.BoundedSemaphore(2)
    monkeypatch.setattr(extract, "_parser_slots", slots)
    real_parse_reply = extract._parse_reply
    free_while_decoding = []

    def counting_parse_reply(reply):
        taken = [slots.acquire(blocking=False) for _ in range(2)]
        free_while_decoding.append(sum(taken))
        for got in taken:
            if got:
                slots.release()
        return real_parse_reply(reply)

    monkeypatch.setattr(extract, "_parse_reply", counting_parse_reply)
    run_stub("cwd")
    assert free_while_decoding == [1]  # one of the two slots is still this request's


def test_running_out_of_memory_while_decoding_the_reply_is_busy_not_500(monkeypatch):
    def no_memory(_reply):
        raise MemoryError

    monkeypatch.setattr(extract, "_parse_reply", no_memory)
    with pytest.raises(ParserBusyError):
        run_stub("cwd")


def test_a_worker_that_answers_before_reading_its_input_keeps_its_answer():
    for _ in range(5):  # the race needs the server to still be writing when the worker exits
        with pytest.raises(UnreadableFileError, match="no selectable text"):
            run_parser(
                "reply-without-reading", b"x" * 4_000_000, timeout=10.0, cpu_seconds=10, module=STUB
            )


def test_the_worker_does_not_import_from_its_working_directory():
    text, _ = run_stub("sys-path")
    path = json.loads(text)
    assert "/" not in path and "" not in path
    assert str(extract._PROJECT_ROOT) in path  # the app itself is still importable


@pytest.mark.parametrize("length", [-1, "2", True, None])
def test_a_header_announcing_an_impossible_length_is_malformed(length):
    with pytest.raises(extract._MalformedReplyError):
        extract._expected_size(bytearray(json.dumps({"length": length}).encode() + b"\n"))


def test_reading_after_the_deadline_is_capped(monkeypatch):
    monkeypatch.setattr(extract, "LATE_READ_BYTES", 100)
    read_end, write_end = os.pipe()
    os.write(write_end, json.dumps({"length": 10_000}).encode() + b"\n" + b"z" * 300)

    class StillWritingWorker:
        stdout = os.fdopen(read_end, "rb")

    try:
        with StillWritingWorker.stdout, pytest.raises(TimeoutError):
            extract._read_reply(StillWritingWorker, time.monotonic() - 1)
    finally:
        os.close(write_end)


def test_a_worker_without_a_stdout_pipe_is_a_server_error():
    class NoPipe:
        stdout = None

    with pytest.raises(RuntimeError):
        extract._read_reply(NoPipe, time.monotonic() + 1)


def test_a_worker_that_cannot_be_started_is_busy(monkeypatch):
    def out_of_processes(*_args, **_kwargs):
        raise OSError("Resource temporarily unavailable")

    monkeypatch.setattr(extract.subprocess, "Popen", out_of_processes)
    with pytest.raises(ParserBusyError):
        run_stub("cwd")


def test_a_reply_that_is_not_utf8_is_unreadable():
    body = b"\xff\xfe"
    reply = json.dumps({"status": "ok", "pages": 1, "length": len(body)}).encode() + b"\n" + body
    with pytest.raises(UnreadableFileError, match="could not be read"):
        extract._parse_reply(reply)
