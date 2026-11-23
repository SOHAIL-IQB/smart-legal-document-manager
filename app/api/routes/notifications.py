from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.db.models import Notification
from app.schemas.activity import NotificationItem, NotificationPage, ReadAllResponse, UnreadCount
from app.services import notifications as notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _item(notification: Notification) -> NotificationItem:
    return NotificationItem(
        id=notification.id,
        kind=notification.kind,
        message=notification.message,
        document_id=notification.document_id,
        version_number=notification.version_number,
        actor_id=notification.actor_id,
        actor_name=notification.actor.name if notification.actor else None,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.get("", response_model=NotificationPage)
def list_notifications(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationPage:
    """My notifications, newest first."""
    items, total = notification_service.list_notifications(
        db, user, unread_only=unread_only, limit=limit, offset=offset
    )
    return NotificationPage(
        items=[_item(n) for n in items],
        total=total,
        unread=notification_service.unread_count(db, user),
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: CurrentUser, db: DbSession) -> UnreadCount:
    return UnreadCount(unread=notification_service.unread_count(db, user))


@router.post("/read-all", response_model=ReadAllResponse)
def mark_all_read(user: CurrentUser, db: DbSession) -> ReadAllResponse:
    return ReadAllResponse(updated=notification_service.mark_all_read(db, user))


@router.post("/{notification_id}/read", response_model=NotificationItem)
def mark_read(notification_id: int, user: CurrentUser, db: DbSession) -> NotificationItem:
    return _item(notification_service.mark_read(db, user, notification_id))
