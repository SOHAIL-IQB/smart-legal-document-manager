from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.models import DocumentVersion
from app.db.session import get_db
from app.notifications.notification_service import send_notification
from app.schemas.common import MessageResponse
from app.schemas.document import (
    DocumentVersionCreate,
    DocumentVersionCreateResponse,
    DocumentVersionResponse,
)
from app.services import versions as version_service

router = APIRouter(prefix="/documents", tags=["versions"])


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Content was identical; no version created."}},
)
def create_version(
    document_id: int,
    payload: DocumentVersionCreate,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
) -> DocumentVersionCreateResponse:
    result = version_service.create_version(
        db, document_id=document_id, content=payload.content, user_id=payload.user_id
    )
    if result.version is None:
        response.status_code = status.HTTP_200_OK
    elif result.meaningful:
        background_tasks.add_task(
            send_notification,
            document_id=document_id,
            user_name=result.editor.name,
            version_number=result.version.version_number,
        )

    return DocumentVersionCreateResponse(
        message=result.message,
        document_id=document_id,
        version=result.version.version_number if result.version else None,
    )


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
def list_versions(document_id: int, db: Session = Depends(get_db)) -> list[DocumentVersion]:
    return version_service.list_versions(db, document_id)


@router.delete("/{document_id}/versions/{version_number}", response_model=MessageResponse)
def delete_version(
    document_id: int, version_number: int, db: Session = Depends(get_db)
) -> MessageResponse:
    version_service.delete_version(db, document_id=document_id, version_number=version_number)
    return MessageResponse(
        message=f"Version {version_number} of document {document_id} deleted successfully."
    )
