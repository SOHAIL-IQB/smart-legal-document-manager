from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.models import DocumentVersion
from app.database.session import get_db
from app.notifications.notification_service import send_notification
from app.schemas.document_schema import (
    DeleteResponse,
    DocumentVersionCreate,
    DocumentVersionCreateResponse,
    DocumentVersionResponse,
)
from app.services.document_service import get_document_or_404, get_user_or_404, list_versions_stmt
from app.services.version_service import create_document_version, delete_document_version
from app.utils.diff_utils import has_meaningful_changes


router = APIRouter(prefix="/documents", tags=["versions"])


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    document_id: int,
    payload: DocumentVersionCreate,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
) -> DocumentVersionCreateResponse:
    try:
        document = get_document_or_404(db, document_id)
        latest_version = document.versions[-1] if document.versions else None
        message, version = create_document_version(
            db,
            document_id=document_id,
            content=payload.content,
            user_id=payload.user_id,
        )
        if version and latest_version and has_meaningful_changes(latest_version.content, payload.content):
            user = get_user_or_404(db, payload.user_id)
            background_tasks.add_task(
                send_notification,
                document_id=document_id,
                user_name=user.name,
                version_number=version.version_number,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if version is None:
        response.status_code = status.HTTP_200_OK

    return DocumentVersionCreateResponse(
        message=message,
        document_id=document_id,
        version=version.version_number if version else None,
    )


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
def list_versions(document_id: int, db: Session = Depends(get_db)) -> list[DocumentVersion]:
    try:
        get_document_or_404(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return list(db.scalars(list_versions_stmt(document_id)).all())


@router.delete("/{document_id}/versions/{version_number}", response_model=DeleteResponse)
def remove_version(
    document_id: int,
    version_number: int,
    db: Session = Depends(get_db),
) -> DeleteResponse:
    try:
        delete_document_version(db, document_id=document_id, version_number=version_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DeleteResponse(
        message=f"Version {version_number} for document {document_id} deleted successfully."
    )
