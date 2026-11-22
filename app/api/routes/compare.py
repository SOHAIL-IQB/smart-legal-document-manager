from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import CompareResponse
from app.services.versions import compare_versions

router = APIRouter(prefix="/documents", tags=["comparison"])


@router.get("/{document_id}/compare", response_model=CompareResponse)
def compare_document_versions(
    document_id: int,
    v1: int = Query(..., ge=1, description="Version to compare from."),
    v2: int = Query(..., ge=1, description="Version to compare to."),
    db: Session = Depends(get_db),
) -> CompareResponse:
    return CompareResponse(**compare_versions(db, document_id=document_id, v1=v1, v2=v2))
