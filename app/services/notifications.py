"""The notification inbox. Like activity events, notifications are added in the same
transaction as the action that causes them."""

from collections.abc import Iterable

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.db.models import (
    Document,
    DocumentMember,
    Notification,
    NotificationKind,
    User,
    utcnow,
)

# Names (255) and titles (255) can together outrun the column; Postgres would refuse the row
# and with it the whole action (review finding M3).
MAX_MESSAGE_CHARS = Notification.__table__.c.message.type.length


def _fit(message: str) -> str:
    if len(message) <= MAX_MESSAGE_CHARS:
        return message
    return message[: MAX_MESSAGE_CHARS - 1] + "…"


def notify(
    db: Session,
    *,
    user_ids: Iterable[int],
    kind: NotificationKind,
    message: str,
    actor: User,
    document: Document | None = None,
    version_number: int | None = None,
) -> None:
    for user_id in user_ids:
        db.add(
            Notification(
                user_id=user_id,
                document_id=document.id if document else None,
                actor_id=actor.id,
                kind=kind.value,
                message=_fit(message),
                version_number=version_number,
            )
        )


def other_member_ids(db: Session, document_id: int, actor: User) -> list[int]:
    return list(
        db.scalars(
            select(DocumentMember.user_id).where(
                DocumentMember.document_id == document_id, DocumentMember.user_id != actor.id
            )
        )
    )


def _mine(user: User) -> ColumnElement[bool]:
    return Notification.user_id == user.id


def unread_count(db: Session, user: User) -> int:
    stmt = select(func.count(Notification.id)).where(_mine(user), Notification.read_at.is_(None))
    return db.scalar(stmt) or 0


def list_notifications(
    db: Session, user: User, *, unread_only: bool, limit: int, offset: int
) -> tuple[list[Notification], int]:
    conditions = [_mine(user)]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    total = db.scalar(select(func.count(Notification.id)).where(*conditions)) or 0
    items = db.scalars(
        select(Notification)
        .options(selectinload(Notification.actor))
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(items), total


def mark_read(db: Session, user: User, notification_id: int) -> Notification:
    notification = db.scalar(
        select(Notification).where(Notification.id == notification_id, _mine(user))
    )
    if notification is None:  # someone else's look exactly like missing ones
        raise NotFoundError(f"Notification {notification_id} was not found.")
    if notification.read_at is None:
        notification.read_at = utcnow()
        db.commit()
    return notification


def mark_all_read(db: Session, user: User) -> int:
    result = db.execute(
        update(Notification)
        .where(_mine(user), Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return result.rowcount or 0
