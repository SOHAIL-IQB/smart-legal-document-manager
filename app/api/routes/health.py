"""Liveness and readiness (audit item B15, Phase 7 T8).

- /health/live: the process is up. Never touches the database, so a database outage doesn't
  make an orchestrator restart healthy API containers.
- /health/ready (and the older /health): the API can serve traffic, i.e. the database answers.
"""

from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError
from app.db.session import engine

router = APIRouter(tags=["health"])


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "unavailable"


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
@router.get("/health")
def readiness() -> dict[str, str]:
    try:
        check_database()
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError("The database is not reachable.") from exc
    return {"status": "ok", "database": "ok"}
