"""Turn an uploaded PDF, DOCX or TXT file into plain text.

Everything here treats the file as hostile:
- The type comes from the file's bytes (magic numbers), and must match the extension. The
  browser's Content-Type is never trusted.
- DOCX archives are size-checked before anything is inflated (zip bombs). python-docx parses XML
  with `resolve_entities=False`, so external-entity (XXE) tricks don't apply.
- PDFs: encrypted files and page counts are checked before text extraction; pypdf has its own
  decompression limits (`LimitReachedError`).
"""

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from fastapi import status

from app.core.errors import AppError
from app.schemas.common import MAX_CONTENT_CHARS

FileKind = Literal["pdf", "docx", "txt"]

MAX_PDF_PAGES = 500
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
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


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line in a row
    return text.strip("\n").strip()


def _pdf_text(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnreadableFileError(
                "This PDF is password-protected. Remove the password and upload it again."
            )
        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise UnreadableFileError(f"PDFs can have at most {MAX_PDF_PAGES} pages.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except UnreadableFileError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, OSError) as exc:
        raise UnreadableFileError("This PDF could not be read. It may be damaged.") from exc

    text = "\n\n".join(normalize_text(page) for page in pages if page.strip())
    if not text.strip():
        raise UnreadableFileError(
            "This PDF has no selectable text (it may be a scan). Text recognition (OCR) "
            "isn't supported yet."
        )
    return text, page_count


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            inflated = sum(info.file_size for info in archive.infolist())
            if inflated > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise UnreadableFileError("This Word file is too large once uncompressed.")
    except zipfile.BadZipFile as exc:
        raise UnreadableFileError("This Word file could not be read. It may be damaged.") from exc

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
    except UnreadableFileError:
        raise
    except Exception as exc:  # python-docx raises many types for malformed packages
        raise UnreadableFileError("This Word file could not be read. It may be damaged.") from exc
    return "\n".join(lines)


def _txt_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnreadableFileError("Text files must be UTF-8 encoded.") from exc


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
    if expected == "pdf":
        raw, pages = _pdf_text(data)
    elif expected == "docx":
        raw = _docx_text(data)
    else:
        raw = _txt_text(data)

    text = normalize_text(raw)
    if not text:
        raise UnreadableFileError("The file contains no text.")
    if len(text) > MAX_TEXT_CHARS:
        raise UnreadableFileError(
            f"The extracted text is longer than {MAX_TEXT_CHARS:,} characters."
        )
    return ExtractedText(text=text, kind=expected, pages=pages)
