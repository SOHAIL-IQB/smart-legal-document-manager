from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession, EditorAccess, OwnerAccess, ViewerAccess
from app.core.errors import AppError
from app.db.models import Document, Role
from app.schemas.common import MessageResponse
from app.schemas.document import (
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentTitleUpdate,
)
from app.services import documents as document_service
from app.services.versions import get_latest_version

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_response(document: Document, role: Role) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        title=document.title,
        created_at=document.created_at,
        updated_at=document.updated_at,
        created_by=document.created_by,
        my_role=role,
    )


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate, user: CurrentUser, db: DbSession
) -> DocumentCreateResponse:
    document, version = document_service.create_document(
        db, title=payload.title, content=payload.content, user=user
    )
    return DocumentCreateResponse(document_id=document.id, version=version.version_number)


@router.get("", response_model=list[DocumentResponse])
def list_documents(user: CurrentUser, db: DbSession) -> list[DocumentResponse]:
    """Documents the signed-in user owns or has been shared on."""
    return [
        _to_response(document, role)
        for document, role in document_service.list_documents_for_user(db, user)
    ]


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(access: ViewerAccess, db: DbSession) -> DocumentDetailResponse:
    document = access.document
    latest = get_latest_version(db, document.id)
    return DocumentDetailResponse(
        **_to_response(document, access.role).model_dump(),
        latest_version=latest.version_number if latest else None,
        version_count=document_service.count_versions(db, document.id),
    )


@router.patch("/{document_id}/title", response_model=DocumentResponse)
def rename_document(
    payload: DocumentTitleUpdate, access: EditorAccess, db: DbSession
) -> DocumentResponse:
    document = document_service.rename_document(db, access.document, title=payload.title)
    return _to_response(document, access.role)


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    access: OwnerAccess,
    db: DbSession,
    confirm: bool = Query(default=False, description="Must be true to delete the document."),
) -> MessageResponse:
    if not confirm:
        raise AppError("Document deletion requires confirm=true.")
    document_id = access.document.id
    document_service.delete_document(db, access.document)
    return MessageResponse(message=f"Document {document_id} deleted successfully.")
