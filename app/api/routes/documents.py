from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession, EditorAccess, OwnerAccess, ViewerAccess
from app.core.errors import AppError
from app.db.models import Role
from app.schemas.common import MessageResponse, NoNul
from app.schemas.document import (
    DocumentCreate,
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentTitleUpdate,
)
from app.services import documents as document_service
from app.services.documents import DocumentSummary, SortField, SortOrder

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_response(summary: DocumentSummary) -> DocumentResponse:
    document = summary.document
    return DocumentResponse(
        id=document.id,
        title=document.title,
        created_at=document.created_at,
        updated_at=document.updated_at,
        created_by=document.created_by,
        created_by_name=summary.created_by_name,
        my_role=summary.role,
        latest_version=summary.latest_version,
        version_count=summary.version_count,
        word_count=summary.word_count,
    )


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate, user: CurrentUser, db: DbSession
) -> DocumentCreateResponse:
    document, version = document_service.create_document(
        db, title=payload.title, content=payload.content, user=user
    )
    return DocumentCreateResponse(document_id=document.id, version=version.version_number)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[
        str | None,
        Query(max_length=200, description="Search titles and the latest content."),
        NoNul,
    ] = None,
    role: Annotated[
        Role | None, Query(description="Only documents where I have this role.")
    ] = None,
    sort: SortField = "updated_at",
    order: SortOrder = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """Documents the signed-in user owns or has been shared on."""
    page, total = document_service.search_documents(
        db, user, query=q, role=role, sort=sort, order=order, limit=limit, offset=offset
    )
    return DocumentListResponse(
        items=[_to_response(summary) for summary in page], total=total, limit=limit, offset=offset
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(access: ViewerAccess, db: DbSession) -> DocumentResponse:
    return _to_response(document_service.get_document_summary(db, access))


@router.patch("/{document_id}/title", response_model=DocumentResponse)
def rename_document(
    payload: DocumentTitleUpdate, access: EditorAccess, db: DbSession
) -> DocumentResponse:
    document_service.rename_document(db, access.document, title=payload.title, actor=access.user)
    return _to_response(document_service.get_document_summary(db, access))


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    access: OwnerAccess,
    db: DbSession,
    confirm: bool = Query(default=False, description="Must be true to delete the document."),
) -> MessageResponse:
    if not confirm:
        raise AppError("Document deletion requires confirm=true.")
    document_id = access.document.id
    document_service.delete_document(db, access.document, actor=access.user)
    return MessageResponse(message=f"Document {document_id} deleted successfully.")
