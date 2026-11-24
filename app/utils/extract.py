"""Turn an uploaded PDF, DOCX or TXT file into plain text.

Everything here treats the file as hostile:
- The type comes from the file's bytes (magic numbers), and must match the extension. The
  browser's Content-Type is never trusted.
- DOCX archives are size-checked before anything is inflated (zip bombs). python-docx parses XML
  with `resolve_entities=False`, so external-entity (XXE) tricks don't apply.
- PDFs: encrypted files and page counts are checked before text extraction; pypdf has its own
  decompression limits (`LimitReachedError`).
"""

import contextlib
import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import IO, Literal

from fastapi import status

from app.core.errors import AppError
from app.schemas.common import MAX_CONTENT_CHARS
from app.utils.parse_worker import MAX_PDF_PAGES, MAX_REPLY_BYTES, normalize_text

FileKind = Literal["pdf", "docx", "txt"]

MAX_TEXT_CHARS = MAX_CONTENT_CHARS

_EXTENSIONS: dict[str, FileKind] = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"


class UnsupportedFileError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"


class UnreadableFileError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "unreadable_file"


@dataclass(frozen=True)
class ExtractedText:
    text: str
    kind: FileKind
    pages: int | None = None  # PDFs only


def safe_filename(raw: str | None) -> str:
    """Keep only the base name, without control characters; never used as a filesystem path."""
    name = PureWindowsPath(PurePosixPath(raw or "").name).name
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    return name[:255] or "upload"


def _detect(data: bytes) -> FileKind | None:
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_ZIP_MAGIC):
        return "docx"
    if b"\x00" in data[:8192]:
        return None  # binary
    return "txt"


def _txt_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnreadableFileError("Text files must be UTF-8 encoded.") from exc


# --- Parsing in a separate worker process (review finding R5) --------------------------------
#
# pypdf caps decompression but not CPU time, and lxml/libxml2 parse hostile input in C, so
# PDF/DOCX parsing runs in `app.utils.parse_worker` as a separate, short-lived process:
# - file in on stdin, a JSON header plus plain UTF-8 text out on stdout (no pickle: a compromised
#   worker can't run code in the server), and reason codes rather than messages;
# - a scrubbed environment: no SECRET_KEY, DATABASE_URL or other secrets in the worker;
# - one deadline covering waiting for a slot, start-up, parsing and reading the reply;
# - a byte cap on the reply, so the server's memory is bounded even if the worker isn't;
# - CPU-time and address-space limits inside the worker (`resource`, Unix);
# - at most PARSE_MAX_CONCURRENT workers at once; beyond that the API answers 503 busy.
# Design and the adversarial review that led to it: LOG.md entry 014.

PARSE_TIMEOUT_SECONDS = 20.0  # parse deadline, counted from when a worker slot is free
PARSE_SLOT_WAIT_SECONDS = 5.0  # how long to wait for a free slot before answering 503
PARSE_CPU_SECONDS = 20
PARSE_MEMORY_BYTES = 1024 * 1024 * 1024  # address space for the worker
PARSE_MAX_CONCURRENT = 4
MAX_REPLY_HEADER_BYTES = 4096
MAX_WORKER_OUTPUT_BYTES = MAX_REPLY_HEADER_BYTES + MAX_REPLY_BYTES
# After the deadline, read only what a worker that already finished could have left in the pipe
# (a pipe holds 64 KiB on Linux); a worker still writing at that point has run out of time.
LATE_READ_BYTES = 1024 * 1024
WORKER_MODULE = "app.utils.parse_worker"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_parser_slots = threading.BoundedSemaphore(PARSE_MAX_CONCURRENT)

_MESSAGES = {
    "encrypted": "This PDF is password-protected. Remove the password and upload it again.",
    "too_many_pages": f"PDFs can have at most {MAX_PDF_PAGES} pages.",
    "no_text": "This PDF has no selectable text (it may be a scan). Text recognition (OCR) "
    "isn't supported yet.",
    "damaged": "This file could not be read. It may be damaged.",
    "too_large_uncompressed": "This Word file is too large once uncompressed.",
    "too_long": "The text in this file is too long to store.",
}
_COULD_NOT_READ = "This file could not be read. It may be damaged."
_BUSY = "The server is busy reading other files. Try again in a minute."


class ParserBusyError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "busy"


class _ReplyTooLongError(Exception):
    pass


class _MalformedReplyError(Exception):
    pass


def _worker_env() -> dict[str, str]:
    """Only what Python needs to start; nothing from the server's own environment."""
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "PYTHONPATH": str(_PROJECT_ROOT),  # the worker runs from "/", so name where the code is
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _feed(stream: IO[bytes], data: bytes) -> None:
    try:
        stream.write(data)
        stream.close()
    except (OSError, ValueError):
        pass  # the worker exited (or was killed) early; its reply, or lack of one, says why


def _expected_size(buffer: bytearray) -> int | None:
    """Total reply size the header announces; None until the header line has arrived.

    Looks at no more than the first MAX_REPLY_HEADER_BYTES, and rejects a bad header at once, so
    a hostile reply can't make the server re-parse a growing buffer on every chunk.
    """
    end = buffer.find(b"\n", 0, MAX_REPLY_HEADER_BYTES + 1)
    if end < 0:
        if len(buffer) > MAX_REPLY_HEADER_BYTES:
            raise _MalformedReplyError  # no real header is this long
        return None
    try:
        length = json.loads(buffer[:end])["length"]
    except (ValueError, KeyError, TypeError, RecursionError):
        raise _MalformedReplyError from None
    if not isinstance(length, int) or isinstance(length, bool) or length < 0:
        raise _MalformedReplyError
    return end + 1 + length


def _read_reply(process: subprocess.Popen[bytes], deadline: float) -> bytes:
    if process.stdout is None:  # always set: stdout=PIPE
        raise RuntimeError("worker stdout is not a pipe")
    buffer = bytearray()  # appending to bytes would copy the whole reply for every chunk
    expected: int | None = None
    late_bytes = 0
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            if expected is None:
                expected = _expected_size(buffer)
            if expected is not None and len(buffer) >= expected:
                return bytes(buffer)  # complete: don't wait for the worker to exit
            remaining = deadline - time.monotonic()
            # At or past the deadline this only polls, so a reply already waiting is still read.
            if not selector.select(max(remaining, 0)):
                raise TimeoutError
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                return bytes(buffer)  # EOF: complete or not, _parse_reply decides
            buffer.extend(chunk)
            if len(buffer) > MAX_WORKER_OUTPUT_BYTES:
                raise _ReplyTooLongError
            if remaining <= 0:
                late_bytes += len(chunk)
                if late_bytes > LATE_READ_BYTES:
                    raise TimeoutError


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the worker and anything it started (it leads its own process group)."""
    with contextlib.suppress(ProcessLookupError, PermissionError):  # already gone
        os.killpg(process.pid, signal.SIGKILL)


def run_parser(
    kind: str,
    data: bytes,
    *,
    timeout: float,
    cpu_seconds: float,
    slot_wait: float = PARSE_SLOT_WAIT_SECONDS,
    module: str = WORKER_MODULE,
) -> tuple[str, int | None]:
    if not _parser_slots.acquire(timeout=slot_wait):
        raise ParserBusyError(_BUSY)
    try:
        deadline = time.monotonic() + timeout  # starts once a slot is free
        reply = _run_worker(module, kind, data, deadline, int(cpu_seconds))
        try:  # decode inside the slot, so the slot count also bounds this peak in memory
            return _parse_reply(reply)
        except MemoryError as exc:
            raise ParserBusyError(_BUSY) from exc
    finally:
        _parser_slots.release()


def _run_worker(module: str, kind: str, data: bytes, deadline: float, cpu_seconds: int) -> bytes:
    try:
        process = subprocess.Popen(  # noqa: S603  [W3]
            # -P: don't put the working directory on the import path (PYTHONPATH names the app).
            [sys.executable, "-P", "-m", module, kind, str(cpu_seconds), str(PARSE_MEMORY_BYTES)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_worker_env(),
            cwd="/",  # no project files relative to where it runs
            start_new_session=True,  # its own process group, killed as a whole below
        )
    except (OSError, subprocess.SubprocessError) as exc:  # e.g. out of processes or memory
        raise ParserBusyError(_BUSY) from exc

    try:
        with process:
            if process.stdin is None:  # always set: stdin=PIPE
                raise RuntimeError("worker stdin is not a pipe")
            writer = threading.Thread(target=_feed, args=(process.stdin, data), daemon=True)
            try:
                writer.start()
                return _read_reply(process, deadline)
            finally:
                _kill_group(process)
                process.wait()
                # The writer finishes (its write fails once the worker is gone) before
                # Popen.__exit__ closes stdin: a close racing the writer can raise BrokenPipeError.
                if writer.ident is not None:  # it started
                    writer.join(timeout=1)
    except TimeoutError:
        raise UnreadableFileError(
            "This file took too long to read. It may be damaged or deliberately complex."
        ) from None
    except _ReplyTooLongError:
        raise UnreadableFileError(_MESSAGES["too_long"]) from None
    except _MalformedReplyError:
        raise UnreadableFileError(_COULD_NOT_READ) from None
    except (OSError, RuntimeError, subprocess.SubprocessError, MemoryError) as exc:
        raise ParserBusyError(_BUSY) from exc  # the server, not the file, ran out of something


def _parse_reply(reply: bytes) -> tuple[str, int | None]:
    header_line, _, body = reply.partition(b"\n")
    try:
        header = json.loads(header_line)
    except (ValueError, RecursionError):
        raise UnreadableFileError(_COULD_NOT_READ) from None
    if not isinstance(header, dict) or header.get("length") != len(body):
        raise UnreadableFileError(_COULD_NOT_READ)  # malformed, or cut off mid-reply
    status_ = header.get("status")
    if status_ == "refused":
        reason = header.get("reason")
        message = _MESSAGES.get(reason, _COULD_NOT_READ) if isinstance(reason, str) else None
        raise UnreadableFileError(message or _COULD_NOT_READ)
    pages = header.get("pages")
    valid_pages = pages is None or (
        isinstance(pages, int) and not isinstance(pages, bool) and pages >= 0
    )
    if status_ != "ok" or not valid_pages:
        raise UnreadableFileError(_COULD_NOT_READ)
    try:
        return body.decode("utf-8"), pages
    except UnicodeDecodeError:
        raise UnreadableFileError(_COULD_NOT_READ) from None


def extract_text(filename: str | None, data: bytes) -> ExtractedText:
    extension = PurePosixPath(safe_filename(filename)).suffix.lower()
    expected = _EXTENSIONS.get(extension)
    if expected is None:
        raise UnsupportedFileError("Upload a .pdf, .docx or .txt file.")

    detected = _detect(data)
    if detected is None and expected == "txt":
        raise UnsupportedFileError("This .txt file contains binary data.")
    if detected != expected:
        raise UnsupportedFileError(f"The file's contents do not match its {extension} extension.")

    pages: int | None = None
    if expected == "txt":
        raw = _txt_text(data)  # decoding only; no parser to sandbox
    else:
        raw, pages = run_parser(
            expected, data, timeout=PARSE_TIMEOUT_SECONDS, cpu_seconds=PARSE_CPU_SECONDS
        )

    text = normalize_text(raw)
    if not text:
        raise UnreadableFileError("The file contains no text.")
    if len(text) > MAX_TEXT_CHARS:
        raise UnreadableFileError(
            f"The extracted text is longer than {MAX_TEXT_CHARS:,} characters."
        )
    return ExtractedText(text=text, kind=expected, pages=pages)
