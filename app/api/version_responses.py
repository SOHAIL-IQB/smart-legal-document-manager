"""Shared by the routes that create versions (typed, restored and uploaded)."""

from fastapi import BackgroundTasks, Response, status

from app.notifications.notification_service import send_notification
from app.schemas.document import DocumentVersionCreateResponse
from app.services.documents import DocumentAccess
from app.services.versions import VersionCreateResult


def respond_to_version_result(
    result: VersionCreateResult,
    access: DocumentAccess,
    response: Response,
    background_tasks: BackgroundTasks,
) -> DocumentVersionCreateResponse:
    document_id = access.document.id
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
