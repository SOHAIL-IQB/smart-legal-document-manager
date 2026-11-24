"""Phase 5: creating documents and versions from PDF, DOCX and TXT files."""

import pytest

from app.core.config import get_settings
from app.utils.extract import (
    UnreadableFileError,
    UnsupportedFileError,
    extract_text,
    safe_filename,
)
from tests.files import (
    make_blank_pdf,
    make_docx,
    make_encrypted_pdf,
    make_pdf,
    make_zip_bomb_docx,
)

# --- extraction (unit) --------------------------------------------------------------


def test_pdf_text_is_extracted_page_by_page():
    result = extract_text("lease.pdf", make_pdf("Clause 1. Rent.\nClause 2. Term.", "Page two."))
    assert result.kind == "pdf"
    assert result.pages == 2
    assert result.text == "Clause 1. Rent.\nClause 2. Term.\n\nPage two."


def test_docx_paragraphs_and_tables_are_extracted_in_order():
    data = make_docx("Agreement", "Parties below.", table=[["Name", "Role"], ["Acme", "Buyer"]])
    result = extract_text("nda.docx", data)
    assert result.kind == "docx"
    assert result.text == "Agreement\nParties below.\nName | Role\nAcme | Buyer"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"Line one\r\nLine two\r\n", "Line one\nLine two"),
        ("﻿With BOM".encode(), "With BOM"),
        ("Café — §4".encode(), "Café — §4"),
        (b"A   \n\n\n\n\nB\t ", "A\n\nB"),  # trailing spaces trimmed, blank runs collapsed
    ],
)
def test_txt_is_decoded_and_normalized(raw, expected):
    result = extract_text("notes.txt", raw)
    assert (result.kind, result.text) == ("txt", expected)


def test_type_is_detected_from_content_and_must_match_extension():
    with pytest.raises(UnsupportedFileError, match="do not match"):
        extract_text("contract.docx", make_pdf("Really a PDF"))
    with pytest.raises(UnsupportedFileError, match="do not match"):
        extract_text("contract.pdf", make_docx("Really a DOCX"))


@pytest.mark.parametrize("name", ["contract.exe", "contract.doc", "contract", "archive.zip"])
def test_unsupported_extensions_are_refused(name):
    with pytest.raises(UnsupportedFileError):
        extract_text(name, b"anything")


def test_binary_data_named_txt_is_refused():
    with pytest.raises(UnsupportedFileError):
        extract_text("notes.txt", b"\x00\x01\x02binary\xff\xfe")


def test_non_utf8_text_is_refused():
    with pytest.raises(UnreadableFileError, match="UTF-8"):
        extract_text("notes.txt", "café".encode("latin-1"))


def test_encrypted_pdf_is_refused():
    with pytest.raises(UnreadableFileError, match="password"):
        extract_text("secret.pdf", make_encrypted_pdf())


def test_pdf_without_text_is_refused_with_a_clear_message():
    with pytest.raises(UnreadableFileError, match="no selectable text"):
        extract_text("scan.pdf", make_blank_pdf())


def test_corrupt_pdf_is_refused():
    with pytest.raises(UnreadableFileError):
        extract_text("broken.pdf", b"%PDF-1.4\nthis is not really a pdf")


def test_corrupt_docx_is_refused():
    with pytest.raises(UnreadableFileError):
        extract_text("broken.docx", b"PK\x03\x04 truncated zip")


def test_zip_bomb_docx_is_refused_before_inflating():
    with pytest.raises(UnreadableFileError, match="too large"):
        extract_text("bomb.docx", make_zip_bomb_docx(uncompressed_mb=60))


def test_too_many_pdf_pages_is_refused():
    # A real 501-page file: parsing runs in a separate process (Phase 7 T6), so patching the limit
    # in this process would not reach it.
    with pytest.raises(UnreadableFileError, match="pages"):
        extract_text("long.pdf", make_pdf(*[f"Page {n}" for n in range(1, 502)]))


@pytest.mark.parametrize("data", [b"", b"   \n\t  \n"])
def test_empty_files_are_refused(data):
    with pytest.raises(UnreadableFileError, match="no text"):
        extract_text("empty.txt", data)


# --- API ---------------------------------------------------------------------------------


def upload(client, account, path, name, data, **form):
    return client.post(
        path,
        files={"file": (name, data, "application/octet-stream")},
        data=form,
        headers=account.headers,
    )


def test_create_document_from_pdf(client, alice):
    response = upload(client, alice, "/api/documents/upload", "Lease 2026.pdf", make_pdf("Rent."))
    assert response.status_code == 201
    document_id = response.json()["document_id"]

    detail = client.get(f"/api/documents/{document_id}", headers=alice.headers).json()
    assert detail["title"] == "Lease 2026"  # defaults to the file name without extension
    version = client.get(f"/api/documents/{document_id}/versions/1", headers=alice.headers).json()
    assert version["content"] == "Rent."
    assert version["source"] == "upload"
    assert version["source_filename"] == "Lease 2026.pdf"


def test_create_document_from_docx_with_explicit_title(client, alice):
    response = upload(
        client, alice, "/api/documents/upload", "nda.docx", make_docx("Terms."), title="  NDA  "
    )
    assert response.status_code == 201
    detail = client.get(f"/api/documents/{response.json()['document_id']}", headers=alice.headers)
    assert detail.json()["title"] == "NDA"


def test_upload_new_version_with_note(client, alice, make_document):
    document_id = make_document(alice, content="Rent.")
    response = upload(
        client,
        alice,
        f"/api/documents/{document_id}/versions/upload",
        "v2.txt",
        b"Rent, due monthly.",
        change_note="Client markup",
    )
    assert response.status_code == 201
    assert response.json()["version"] == 2
    version = client.get(f"/api/documents/{document_id}/versions/2", headers=alice.headers).json()
    assert (version["source"], version["change_note"]) == ("upload", "Client markup")


def test_uploading_identical_content_creates_no_version(client, alice, make_document):
    document_id = make_document(alice, content="Rent.")
    response = upload(
        client, alice, f"/api/documents/{document_id}/versions/upload", "same.txt", b"Rent."
    )
    assert response.status_code == 200
    assert response.json()["message"] == "No changes detected"


def test_version_upload_needs_editor_role(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    document_id = make_document(alice)
    client.post(
        f"/api/documents/{document_id}/members",
        json={"email": bob.email, "role": "viewer"},
        headers=alice.headers,
    )
    response = upload(client, bob, f"/api/documents/{document_id}/versions/upload", "x.txt", b"x")
    assert response.status_code == 403


def test_upload_requires_sign_in(client):
    response = client.post(
        "/api/documents/upload", files={"file": ("a.txt", b"text", "text/plain")}
    )
    assert response.status_code == 401


def test_cookie_upload_needs_csrf_header(client):
    client.post(
        "/api/auth/register",
        json={"name": "C", "email": "c@example.com", "password": "correct horse battery"},
    )
    response = client.post("/api/documents/upload", files={"file": ("a.txt", b"text")})
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("virus.exe", b"MZ", 415, "unsupported_media_type"),
        ("fake.docx", make_pdf("pdf"), 415, "unsupported_media_type"),
        ("scan.pdf", make_blank_pdf(), 422, "unreadable_file"),
        ("secret.pdf", make_encrypted_pdf(), 422, "unreadable_file"),
    ],
)
def test_bad_files_get_clear_errors(client, alice, name, data, status, code):
    response = upload(client, alice, "/api/documents/upload", name, data)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_oversized_upload_is_refused_with_413(client, alice, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 1024)
    response = upload(client, alice, "/api/documents/upload", "big.txt", b"a " * 4096)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_extracted_text_over_the_content_limit_is_refused(client, alice, monkeypatch):
    monkeypatch.setattr("app.utils.extract.MAX_TEXT_CHARS", 10)
    response = upload(client, alice, "/api/documents/upload", "long.txt", b"x" * 50)
    assert response.status_code == 422


def test_missing_file_field_is_422(client, alice):
    response = client.post("/api/documents/upload", data={"title": "x"}, headers=alice.headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "sent",
    [
        "../../etc/Lease.txt",
        "C:\\Users\\bob\\Lease.txt",
        "/var/tmp/Lease.txt",  # noqa: S108 (a filename sent to the API, not a temp file)
    ],
)
def test_path_components_are_stripped_from_the_filename(client, alice, sent):
    response = upload(client, alice, "/api/documents/upload", sent, b"Rent.")
    assert response.status_code == 201
    document_id = response.json()["document_id"]
    version = client.get(f"/api/documents/{document_id}/versions/1", headers=alice.headers).json()
    assert version["source_filename"] == "Lease.txt"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Lease\x00.txt", "Lease.txt"),
        ("a\nb\r.pdf", "ab.pdf"),
        ("", "upload"),
        ("x" * 300, "x" * 255),
    ],
)
def test_safe_filename_removes_control_characters_and_caps_length(raw, expected):
    # httpx percent-encodes control characters, so this is checked below the HTTP layer.
    assert safe_filename(raw) == expected


def test_declared_oversized_upload_is_refused_before_the_route_runs(client, alice, monkeypatch):
    def route_must_not_run(*_args, **_kwargs):
        raise AssertionError("the body was parsed and the route ran")

    monkeypatch.setattr("app.api.routes.uploads._read_and_extract", route_must_not_run)
    big = b"a" * (get_settings().max_upload_bytes + 128 * 1024)  # over limit + multipart room
    response = upload(client, alice, "/api/documents/upload", "big.txt", big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
