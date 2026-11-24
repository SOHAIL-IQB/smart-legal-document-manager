"""Document sharing: list, add, change and remove members. Rules in docs/adr/0001."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.db.models import DocumentMember, NotificationKind, Role, User
from app.services.activity import record
from app.services.documents import DocumentAccess
from app.services.notifications import notify
from app.services.users import find_user_by_email


def list_members(db: Session, document_id: int) -> list[tuple[DocumentMember, User]]:
    rows = db.execute(
        select(DocumentMember, User)
        .join(User, User.id == DocumentMember.user_id)
        .where(DocumentMember.document_id == document_id)
        .order_by(DocumentMember.added_at.asc(), User.id.asc())
    ).all()
    return [(member, user) for member, user in rows]


def _get_member(db: Session, document_id: int, user_id: int) -> DocumentMember:
    member = db.get(DocumentMember, (document_id, user_id))
    if member is None:
        raise NotFoundError(f"User {user_id} is not a member of this document.")
    return member


def _owner_count(db: Session, document_id: int) -> int:
    # FOR UPDATE locks the owner rows (Postgres), so two owners demoting each other at the
    # same moment can't both pass this check and leave the document ownerless.
    stmt = (
        select(DocumentMember.user_id)
        .where(DocumentMember.document_id == document_id, DocumentMember.role == Role.OWNER.value)
        .with_for_update()
    )
    return len(db.scalars(stmt).all())


def _ensure_not_last_owner(db: Session, member: DocumentMember) -> None:
    if member.role == Role.OWNER.value and _owner_count(db, member.document_id) <= 1:
        raise ConflictError("A document must keep at least one owner.")


def add_member(
    db: Session, access: DocumentAccess, *, email: str, role: Role
) -> tuple[DocumentMember, User]:
    user = find_user_by_email(db, email)
    # A deleted account's placeholder email is predictable; it must not become a member
    # (review finding M1), and it answers exactly like an email with no account.
    if user is None or user.deleted_at is not None:
        raise NotFoundError("No account exists with that email. Ask them to sign up first.")
    if db.get(DocumentMember, (access.document.id, user.id)) is not None:
        raise ConflictError(f"{user.email} already has access to this document.")

    member = DocumentMember(document_id=access.document.id, user_id=user.id, role=role.value)
    db.add(member)
    record(
        db,
        document_id=access.document.id,
        actor=access.user,
        action="member.added",
        user_id=user.id,
        name=user.name,
        role=role.value,
    )
    notify(
        db,
        user_ids=[user.id],
        kind=NotificationKind.DOCUMENT_SHARED,
        message=f"{access.user.name} shared “{access.document.title}” with you as {role.value}.",
        actor=access.user,
        document=access.document,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"{user.email} already has access to this document.") from exc
    db.refresh(member)
    return member, user


def change_role(
    db: Session, access: DocumentAccess, *, user_id: int, role: Role
) -> tuple[DocumentMember, User]:
    member = _get_member(db, access.document.id, user_id)
    previous = member.role
    if previous == role.value:
        return member, member.user
    if role != Role.OWNER:
        _ensure_not_last_owner(db, member)
    member.role = role.value
    record(
        db,
        document_id=access.document.id,
        actor=access.user,
        action="member.role_changed",
        user_id=user_id,
        name=member.user.name,
        **{"from": previous, "to": role.value},
    )
    if user_id != access.user.id:
        notify(
            db,
            user_ids=[user_id],
            kind=NotificationKind.ROLE_CHANGED,
            message=f"{access.user.name} changed your role on “{access.document.title}” "
            f"to {role.value}.",
            actor=access.user,
            document=access.document,
        )
    db.commit()
    return member, member.user


def remove_member(db: Session, access: DocumentAccess, *, user_id: int) -> None:
    """Owners can remove anyone; any member can remove themselves (leave)."""
    if access.role != Role.OWNER and access.user.id != user_id:
        raise PermissionDeniedError("Only an owner can remove other members.")
    member = _get_member(db, access.document.id, user_id)
    _ensure_not_last_owner(db, member)
    left = access.user.id == user_id
    record(
        db,
        document_id=access.document.id,
        actor=access.user,
        action="member.removed",
        user_id=user_id,
        name=member.user.name,
        left=left,
    )
    if not left:
        notify(
            db,
            user_ids=[user_id],
            kind=NotificationKind.REMOVED_FROM_DOCUMENT,
            message=f"{access.user.name} removed you from “{access.document.title}”.",
            actor=access.user,
            document=access.document,
        )
    db.delete(member)
    db.commit()
