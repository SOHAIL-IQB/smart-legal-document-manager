from fastapi import APIRouter, BackgroundTasks, Query, Response, status

from app.api.deps import DbSession, EditorAccess, OwnerAccess, ViewerAccess
from app.api.version_responses import respond_to_version_result
from app.db.models import DocumentVersion
from app.schemas.common import MessageResponse
from app.schemas.document import (
    DocumentVersionCreate,
    DocumentVersionCreateResponse,
    DocumentVersionResponse,
    DocumentVersionSummary,
    RestoreRequest,
)
from app.services import versions as version_service

router = APIRouter(prefix="/documents", tags=["versions"])

_UNCHANGED = {200: {"description": "Content was identical to the latest version; nothing saved."}}


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_UNCHANGED,
)
def create_version(
    payload: DocumentVersionCreate,
    access: EditorAccess,
    background_tasks: BackgroundTasks,
    response: Response,
    db: DbSession,
) -> DocumentVersionCreateResponse:
    result = version_service.create_version(
        db,
        access.document,
        content=payload.content,
        user=access.user,
        change_note=payload.change_note,
    )
    return respond_to_version_result(result, access, response, background_tasks)


@router.get("/{document_id}/versions", response_model=list[DocumentVersionSummary])
def list_versions(
    access: ViewerAccess,
    db: DbSession,
    include_deleted: bool = Query(default=False, description="Also list deleted versions."),
) -> list[DocumentVersion]:
    """Version history without content. Fetch one version to get its text."""
    return version_service.list_versions(db, access.document, include_deleted=include_deleted)


@router.get(
    "/{document_id}/versions/{version_number}",
    response_model=DocumentVersionResponse,
    responses={410: {"description": "The version was deleted."}},
)
def get_version(version_number: int, access: ViewerAccess, db: DbSession) -> DocumentVersion:
    return version_service.get_version(db, access.document.id, version_number)


@router.post(
    "/{document_id}/versions/{version_number}/restore",
    response_model=DocumentVersionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_UNCHANGED,
)
def restore_version(
    version_number: int,
    access: EditorAccess,
    background_tasks: BackgroundTasks,
    response: Response,
    db: DbSession,
    payload: RestoreRequest | None = None,
) -> DocumentVersionCreateResponse:
    """Save a new version with the content of an earlier one. History is never rewritten."""
    result = version_service.restore_version(
        db,
        access.document,
        version_number=version_number,
        user=access.user,
        change_note=payload.change_note if payload else None,
    )
    return respond_to_version_result(result, access, response, background_tasks)


@router.delete("/{document_id}/versions/{version_number}", response_model=MessageResponse)
def delete_version(version_number: int, access: OwnerAccess, db: DbSession) -> MessageResponse:
    """Hide a version. It stays in the audit trail and its number is never reused."""
    document_id = access.document.id
    version_service.delete_version(
        db, access.document, version_number=version_number, user=access.user
    )
    return MessageResponse(
        message=f"Version {version_number} of document {document_id} deleted successfully."
    )
