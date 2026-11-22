from fastapi import APIRouter, Query

from app.api.deps import DbSession, ViewerAccess
from app.schemas.document import CompareResponse
from app.services.versions import compare_versions

router = APIRouter(prefix="/documents", tags=["comparison"])


@router.get("/{document_id}/compare", response_model=CompareResponse)
def compare_document_versions(
    access: ViewerAccess,
    db: DbSession,
    v1: int = Query(..., ge=1, description="Version to compare from."),
    v2: int = Query(..., ge=1, description="Version to compare to."),
) -> CompareResponse:
    return CompareResponse(**compare_versions(db, access.document, v1=v1, v2=v2))
