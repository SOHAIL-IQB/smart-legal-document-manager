from fastapi import APIRouter, BackgroundTasks, Response, status

from app.api.deps import DbSession, EditorAccess, OwnerAccess, ViewerAccess
from app.db.models import DocumentVersion
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
    payload: DocumentVersionCreate,
    access: EditorAccess,
    background_tasks: BackgroundTasks,
    response: Response,
    db: DbSession,
) -> DocumentVersionCreateResponse:
    document_id = access.document.id
    result = version_service.create_version(
        db, access.document, content=payload.content, user=access.user
    )
    if result.version is None:
        response.status_code = status.HTTP_200_OK
    elif result.meaningful:
        background_tasks.add_task(
            send_notification,
            document_id=document_id,
            user_name=access.user.name,
            version_number=result.version.version_number,
        )

    return DocumentVersionCreateResponse(
        message=result.message,
        document_id=document_id,
        version=result.version.version_number if result.version else None,
    )


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
def list_versions(access: ViewerAccess, db: DbSession) -> list[DocumentVersion]:
    return version_service.list_versions(db, access.document)


@router.delete("/{document_id}/versions/{version_number}", response_model=MessageResponse)
def delete_version(version_number: int, access: OwnerAccess, db: DbSession) -> MessageResponse:
    document_id = access.document.id
    version_service.delete_version(db, access.document, version_number=version_number)
    return MessageResponse(
        message=f"Version {version_number} of document {document_id} deleted successfully."
    )
