"""PDF/DOCX parsing in a separate, short-lived process (Phase 7 T6, review finding R5).

Run as `python -m app.utils.parse_worker <kind> <cpu_seconds> <memory_bytes>` by
`app.utils.extract.run_parser`, with the file on stdin and a scrubbed environment (no secrets).

Reply on stdout: one JSON header line, then (for "ok") the UTF-8 text.
    {"status": "ok", "pages": 3}\n<text>
    {"status": "refused", "reason": "no_text"}\n
The parent maps reasons to its own messages, so this process never chooses what a user sees.

This module deliberately imports nothing from the app (no FastAPI, no settings): less to load,
less address space used before parsing starts, nothing secret to read.
"""

import io
import json
import os
import re
import sys
import zipfile

MAX_PDF_PAGES = 500
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
# Largest reply body (UTF-8 bytes); the parent enforces the same cap on what it reads.
MAX_REPLY_BYTES = 16 * 1024 * 1024

REASONS = {
    "encrypted",
    "too_many_pages",
    "no_text",
    "damaged",
    "too_large_uncompressed",
    "too_long",
}


class RefusedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line in a row
    return text.strip("\n").strip()


def pdf_text(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise RefusedError("encrypted")
        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise RefusedError("too_many_pages")
        pages = [page.extract_text() or "" for page in reader.pages]
    except RefusedError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, OSError) as exc:
        raise RefusedError("damaged") from exc

    text = "\n\n".join(normalize_text(page) for page in pages if page.strip())
    if not text.strip():
        raise RefusedError("no_text")
    return text, page_count


def docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            inflated = sum(info.file_size for info in archive.infolist())
            if inflated > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise RefusedError("too_large_uncompressed")
    except zipfile.BadZipFile as exc:
        raise RefusedError("damaged") from exc

    from docx import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = DocxDocument(io.BytesIO(data))
        lines: list[str] = []
        # Walk the body in order so tables stay where they appear in the document.
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                lines.append(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    except Exception as exc:  # python-docx raises many types for malformed packages
        raise RefusedError("damaged") from exc
    return "\n".join(lines)


def limit_resources(cpu_seconds: int, memory_bytes: int, *, allow_fork: bool = False) -> None:
    """Confine this process (Unix; each limit best-effort per platform).

    https://docs.python.org/3.12/library/resource.html. Exceeding RLIMIT_CPU sends SIGXCPU.
    RLIMIT_FSIZE 0: no file writes (Python ignores SIGXFSZ, so writes fail with EFBIG).
    RLIMIT_NPROC 0: no new processes (not enforced for root). macOS refuses an RLIMIT_AS below
    its current maximum, so there memory is unbounded (development only).
    """
    try:
        import resource
    except ImportError:
        return
    limits = [
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_AS, memory_bytes),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 64),
    ]
    if not allow_fork:
        limits.append((resource.RLIMIT_NPROC, 0))
    for limit, value in limits:
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            continue
    try:  # Linux: if memory runs out, the kernel should kill this worker, not the server
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass


def _emit(header: dict[str, object], body: bytes = b"") -> None:
    header = {**header, "length": len(body)}  # lets the parent detect a cut-off reply
    sys.stdout.buffer.write(json.dumps(header).encode() + b"\n" + body)
    sys.stdout.buffer.flush()


def emit_ok(text: str, pages: int | None) -> None:
    # "replace": a hostile file can make the extractor produce lone surrogates.
    _emit({"status": "ok", "pages": pages}, text.encode("utf-8", "replace"))


def emit_refused(reason: str) -> None:
    _emit({"status": "refused", "reason": reason})


def main() -> None:
    kind, cpu_seconds, memory_bytes = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    limit_resources(cpu_seconds, memory_bytes)
    data = sys.stdin.buffer.read()
    try:
        if kind == "pdf":
            text, pages = pdf_text(data)
        elif kind == "docx":
            text, pages = docx_text(data), None
        else:
            raise RefusedError("damaged")
        if len(text.encode("utf-8", "replace")) > MAX_REPLY_BYTES:
            raise RefusedError("too_long")
    except RefusedError as refusal:
        emit_refused(refusal.reason)
    else:
        emit_ok(text, pages)
    # The reply is complete; skip interpreter teardown, which can be slow for big documents.
    os._exit(0)


if __name__ == "__main__":
    main()
