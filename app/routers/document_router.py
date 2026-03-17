from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.models import Document
from app.database.session import get_db
from app.schemas.document_schema import (
    DeleteResponse,
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentTitleUpdate,
)
from app.services.document_service import (
    count_versions,
    get_document_or_404,
    get_latest_version,
    list_documents_stmt,
)
from app.services.version_service import create_document_with_initial_version, delete_document, update_document_title


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
) -> DocumentCreateResponse:
    try:
        document, version = create_document_with_initial_version(
            db,
            title=payload.title,
            content=payload.content,
            user_id=payload.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DocumentCreateResponse(document_id=document.id, version=version.version_number)


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(list_documents_stmt()).all())


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentDetailResponse:
    try:
        document = get_document_or_404(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    latest_version = get_latest_version(db, document_id)
    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        created_at=document.created_at,
        created_by=document.created_by,
        latest_version=latest_version.version_number if latest_version else None,
        version_count=count_versions(db, document_id),
    )


@router.patch("/{document_id}/title", response_model=DocumentResponse)
def patch_title(
    document_id: int,
    payload: DocumentTitleUpdate,
    db: Session = Depends(get_db),
) -> Document:
    try:
        return update_document_title(db, document_id=document_id, title=payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{document_id}", response_model=DeleteResponse)
def remove_document(
    document_id: int,
    confirm: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document deletion requires confirm=true.",
        )

    try:
        delete_document(db, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DeleteResponse(message=f"Document {document_id} deleted successfully.")
