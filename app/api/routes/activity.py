from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, ViewerAccess
from app.schemas.activity import ActivityItem, ActivityPage
from app.services.activity import list_activity

router = APIRouter(prefix="/documents", tags=["activity"])


@router.get("/{document_id}/activity", response_model=ActivityPage)
def document_activity(
    access: ViewerAccess,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActivityPage:
    """Everything that happened to this document, newest first. Read-only by design."""
    events, total = list_activity(db, access.document.id, limit=limit, offset=offset)
    return ActivityPage(
        items=[
            ActivityItem(
                id=event.id,
                action=event.action,
                actor_id=event.actor_id,
                actor_name=event.actor.name,
                details=event.details,
                created_at=event.created_at,
            )
            for event in events
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
