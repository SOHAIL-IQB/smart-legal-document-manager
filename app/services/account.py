"""Export your data, and delete your account (Phase 7 T15; spec addendum in phase-7-hardening.md).

Deleting an account anonymizes it instead of removing the row: documents, versions and the
append-only activity log refer to users, and that history has to stay readable. Names already
written into past activity details and other people's notifications are left as they are
(a recorded trade-off); everything looked up live shows the placeholder name.
"""

import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.security import hash_password
from app.db.models import (
    ActivityEvent,
    Document,
    DocumentMember,
    DocumentVersion,
    Notification,
    Role,
    User,
    utcnow,
)
from app.services.activity import record

DELETED_NAME = "Deleted user"
EXPORT_FORMAT_VERSION = 1


def placeholder_email(user_id: int) -> str:
    # .example is reserved (RFC 2606): never delivers mail, and still passes EmailStr.
    return f"deleted-user-{user_id}@deleted.example"


def export_account(db: Session, user: User) -> dict[str, Any]:
    """Everything about the user, limited to documents they can still access."""
    rows = db.execute(
        select(DocumentMember, Document)
        .join(Document, Document.id == DocumentMember.document_id)
        .where(DocumentMember.user_id == user.id)
        .order_by(Document.id)
    ).all()
    titles = {document.id: document.title for _, document in rows}
    accessible = list(titles)

    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.edited_by == user.id, DocumentVersion.document_id.in_(accessible))
        .order_by(DocumentVersion.document_id, DocumentVersion.version_number)
    )
    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.actor_id == user.id, ActivityEvent.document_id.in_(accessible))
        .order_by(ActivityEvent.id)
    )
    notifications = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id)
    )
    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": utcnow(),
        "profile": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "created_at": user.created_at,
        },
        "memberships": [
            {
                "document_id": document.id,
                "title": document.title,
                "role": member.role,
                "added_at": member.added_at,
            }
            for member, document in rows
        ],
        "versions_authored": [
            {
                "document_id": version.document_id,
                "document_title": titles[version.document_id],
                "version_number": version.version_number,
                "created_at": version.created_at,
                "source": version.source,
                "source_filename": version.source_filename,
                "change_note": version.change_note,
                "deleted_at": version.deleted_at,
                "content": version.content,
            }
            for version in versions
        ],
        "activity": [
            {
                "document_id": event.document_id,
                "action": event.action,
                "details": event.details,
                "created_at": event.created_at,
            }
            for event in events
        ],
        "notifications": [
            {
                "kind": notification.kind,
                "message": notification.message,
                "document_id": notification.document_id,
                "version_number": notification.version_number,
                "created_at": notification.created_at,
                "read_at": notification.read_at,
            }
            for notification in notifications
        ],
    }


@dataclass(frozen=True)
class DeletionSummary:
    documents_deleted: int
    documents_left: int


def delete_account(db: Session, user: User) -> DeletionSummary:
    """Anonymize the account in one transaction, or refuse without changing anything."""
    own = select(DocumentMember.document_id).where(DocumentMember.user_id == user.id)
    members_by_document: dict[int, list[DocumentMember]] = {}
    for member in db.scalars(select(DocumentMember).where(DocumentMember.document_id.in_(own))):
        members_by_document.setdefault(member.document_id, []).append(member)

    alone: list[int] = []
    leaving: list[DocumentMember] = []
    blocking: list[int] = []
    for document_id, members in members_by_document.items():
        mine = next(m for m in members if m.user_id == user.id)
        others = [m for m in members if m.user_id != user.id]
        if not others:
            alone.append(document_id)
        elif mine.role == Role.OWNER and not any(m.role == Role.OWNER for m in others):
            blocking.append(document_id)
        else:
            leaving.append(mine)

    if blocking:
        documents = db.scalars(
            select(Document).where(Document.id.in_(blocking)).order_by(Document.id)
        )
        raise ConflictError(
            "You are the last owner of documents other people still use. Make someone else an "
            "owner, or delete those documents, then try again.",
            details={"documents": [{"id": d.id, "title": d.title} for d in documents]},
        )

    # Anonymize first, so the events recorded below don't write the real name anywhere new.
    user.name = DELETED_NAME
    user.email = placeholder_email(user.id)
    user.password_hash = hash_password(secrets.token_urlsafe(32))  # nobody knows this password
    user.deleted_at = utcnow()

    for document in db.scalars(select(Document).where(Document.id.in_(alone))):
        db.delete(document)  # as DELETE /documents/{id}; nobody else to notify
    for member in leaving:
        record(
            db,
            document_id=member.document_id,
            actor=user,
            action="member.removed",
            user_id=user.id,
            name=DELETED_NAME,
            left=True,
            account_deleted=True,
        )
        db.delete(member)
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.commit()
    return DeletionSummary(documents_deleted=len(alone), documents_left=len(leaving))
