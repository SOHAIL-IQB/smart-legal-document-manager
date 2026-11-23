"""Shared by the routes that create versions (typed, restored and uploaded)."""

from fastapi import Response, status

from app.schemas.document import DocumentVersionCreateResponse
from app.services.documents import DocumentAccess
from app.services.versions import VersionCreateResult


def respond_to_version_result(
    result: VersionCreateResult, access: DocumentAccess, response: Response
) -> DocumentVersionCreateResponse:
    """201 for a new version, 200 when the content was identical and nothing was saved.

    Activity and notifications were already saved in the same transaction as the version.
    """
    if result.version is None:
        response.status_code = status.HTTP_200_OK
    return DocumentVersionCreateResponse(
        message=result.message,
        document_id=access.document.id,
        version=result.version.version_number if result.version else None,
    )
