"""Build small, real PDF / DOCX files in memory for upload tests (no binary fixtures in git)."""

import io
import zipfile

from docx import Document as DocxDocument
from pypdf import PdfReader, PdfWriter


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(*pages: str) -> bytes:
    """A minimal valid PDF with one page per argument; each line becomes a text line."""
    objects: list[bytes] = []
    page_ids = []
    font_id = 3 + 2 * len(pages)
    for index, text in enumerate(pages):
        page_id, content_id = 3 + 2 * index, 4 + 2 * index
        page_ids.append(page_id)
        lines = text.split("\n")
        ops = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]
        for line in lines:
            ops.append(f"({_escape_pdf_text(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        page = (
            f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >> endobj"
        )
        objects.append(page.encode())
        objects.append(
            f"{content_id} 0 obj << /Length {len(stream)} >> stream\n".encode()
            + stream
            + b"\nendstream endobj"
        )
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    head = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        f"2 0 obj << /Type /Pages /Kids [{kids}] /Count {len(pages)} >> endobj".encode(),
    ]
    font = f"{font_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj".encode()
    body = head + objects + [font]

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for obj in body:
        offsets.append(out.tell())
        out.write(obj + b"\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(body) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer << /Size {len(body) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def make_blank_pdf(pages: int = 1) -> bytes:
    """A PDF with no text at all, like a scanned document."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_encrypted_pdf(text: str = "Secret terms.") -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf(text))))
    # RC4 rather than AES: AES needs the `cryptography` package, and the server never decrypts.
    writer.encrypt(user_password="pw", owner_password="owner", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_docx(*paragraphs: str, table: list[list[str]] | None = None) -> bytes:
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if table:
        grid = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, cell in enumerate(row):
                grid.cell(r, c).text = cell
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def make_zip_bomb_docx(uncompressed_mb: int = 60) -> bytes:
    """A .docx-shaped zip whose document.xml inflates to `uncompressed_mb` megabytes."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", b"<w:document>" + b" " * (uncompressed_mb << 20))
    return out.getvalue()
