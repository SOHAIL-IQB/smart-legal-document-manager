from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models import NotificationKind


class ActivityItem(BaseModel):
    id: int
    action: str
    actor_id: int
    actor_name: str
    details: dict[str, Any]
    created_at: datetime


class ActivityPage(BaseModel):
    items: list[ActivityItem]
    total: int
    limit: int
    offset: int


class NotificationItem(BaseModel):
    id: int
    kind: NotificationKind
    message: str
    document_id: int | None  # None once the document has been deleted
    version_number: int | None
    actor_id: int | None
    actor_name: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    total: int
    unread: int
    limit: int
    offset: int


class UnreadCount(BaseModel):
    unread: int


class ReadAllResponse(BaseModel):
    updated: int
