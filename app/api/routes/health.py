from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    # Phase 7 extends this to check the database connection.
    return {"status": "ok"}
