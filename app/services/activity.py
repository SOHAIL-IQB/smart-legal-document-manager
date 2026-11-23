"""The per-document activity log. `record` only adds the row; the caller's commit saves it
together with the action, so a failed action never leaves an event behind."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import ActivityEvent, User


def record(db: Session, *, document_id: int, actor: User, action: str, **details: Any) -> None:
    db.add(
        ActivityEvent(
            document_id=document_id,
            actor_id=actor.id,
            action=action,
            details={key: value for key, value in details.items() if value is not None},
        )
    )


def list_activity(
    db: Session, document_id: int, *, limit: int, offset: int
) -> tuple[list[ActivityEvent], int]:
    where = ActivityEvent.document_id == document_id
    total = db.scalar(select(func.count(ActivityEvent.id)).where(where)) or 0
    events = db.scalars(
        select(ActivityEvent)
        .options(selectinload(ActivityEvent.actor))
        .where(where)
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(events), total
