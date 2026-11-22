"""Create documents and versions from uploaded files. Extraction rules: app/utils/extract.py."""

from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, EditorAccess
from app.api.routes.versions import respond_to_version_result
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import VersionSource
from app.schemas.document import DocumentCreateResponse, DocumentVersionCreateResponse
from app.services import documents as document_service
from app.services import versions as version_service
from app.utils.extract import ExtractedText, extract_text, safe_filename

router = APIRouter(prefix="/documents", tags=["uploads"])

_FILE_HELP = "A .pdf, .docx or .txt file. Only its text is stored."
_ERRORS = {
    413: {"description": "File larger than the upload limit"},
    415: {"description": "Not a PDF, DOCX or TXT file, or the contents don't match the extension"},
    422: {"description": "Encrypted, damaged, scanned (no text) or empty file"},
}


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "payload_too_large"


def _too_large() -> PayloadTooLargeError:
    limit_mb = get_settings().max_upload_bytes / (1024 * 1024)
    return PayloadTooLargeError(f"Files can be at most {limit_mb:g} MB.")


def _read_and_extract(file: UploadFile) -> tuple[ExtractedText, str]:
    """Routes here are plain `def`, so FastAPI runs them (and this parsing) in its threadpool."""
    limit = get_settings().max_upload_bytes
    data = file.file.read(limit + 1)  # covers uploads sent without a Content-Length
    if len(data) > limit:
        raise _too_large()
    name = safe_filename(file.filename)
    return extract_text(name, data), name


def _title(explicit: str | None, filename: str) -> str:
    title = (explicit or "").strip() or PurePosixPath(filename).stem.strip() or "Untitled"
    return title[:255]


@router.post(
    "/upload",
    response_model=DocumentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
def create_document_from_file(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description=_FILE_HELP)],
    title: Annotated[
        str | None, Form(max_length=255, description="Defaults to the file name.")
    ] = None,
) -> DocumentCreateResponse:
    extracted, filename = _read_and_extract(file)
    document, version = document_service.create_document(
        db,
        title=_title(title, filename),
        content=extracted.text,
        user=user,
        source=VersionSource.UPLOAD,
        source_filename=filename,
    )
    return DocumentCreateResponse(document_id=document.id, version=version.version_number)


@router.post(
    "/{document_id}/versions/upload",
    response_model=DocumentVersionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Same text as the latest version; nothing saved."}, **_ERRORS},
)
def create_version_from_file(
    access: EditorAccess,
    db: DbSession,
    background_tasks: BackgroundTasks,
    response: Response,
    file: Annotated[UploadFile, File(description=_FILE_HELP)],
    change_note: Annotated[str | None, Form(max_length=500)] = None,
) -> DocumentVersionCreateResponse:
    extracted, filename = _read_and_extract(file)
    result = version_service.create_version(
        db,
        access.document,
        content=extracted.text,
        user=access.user,
        change_note=(change_note or "").strip() or None,
        source=VersionSource.UPLOAD,
        source_filename=filename,
    )
    return respond_to_version_result(result, access, response, background_tasks)
