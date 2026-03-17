from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.document_schema import CompareResponse
from app.services.diff_service import compare_versions
from app.services.document_service import get_version_or_404


router = APIRouter(prefix="/documents", tags=["comparison"])


@router.get("/{document_id}/compare", response_model=CompareResponse)
def compare_document_versions(
    document_id: int,
    v1: int,
    v2: int,
    db: Session = Depends(get_db),
) -> CompareResponse:
    try:
        version_1 = get_version_or_404(db, document_id, v1)
        version_2 = get_version_or_404(db, document_id, v2)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    comparison = compare_versions(version_1.content, version_2.content)
    return CompareResponse(
        document_id=document_id,
        version_1=v1,
        version_2=v2,
        **comparison,
    )
