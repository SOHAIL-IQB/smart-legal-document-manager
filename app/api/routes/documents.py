from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Document
from app.db.session import get_db
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


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate, db: Session = Depends(get_db)
) -> DocumentCreateResponse:
    document, version = document_service.create_document(
        db, title=payload.title, content=payload.content, user_id=payload.user_id
    )
    return DocumentCreateResponse(document_id=document.id, version=version.version_number)


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return document_service.list_documents(db)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentDetailResponse:
    document = document_service.get_document(db, document_id)
    latest = get_latest_version(db, document_id)
    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        created_at=document.created_at,
        created_by=document.created_by,
        latest_version=latest.version_number if latest else None,
        version_count=document_service.count_versions(db, document_id),
    )


@router.patch("/{document_id}/title", response_model=DocumentResponse)
def rename_document(
    document_id: int, payload: DocumentTitleUpdate, db: Session = Depends(get_db)
) -> Document:
    return document_service.rename_document(db, document_id=document_id, title=payload.title)


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    document_id: int,
    confirm: bool = Query(default=False, description="Must be true to delete the document."),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not confirm:
        raise AppError("Document deletion requires confirm=true.")
    document_service.delete_document(db, document_id=document_id)
    return MessageResponse(message=f"Document {document_id} deleted successfully.")
