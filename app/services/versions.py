"""Version history: create, list, soft-delete, restore and compare.

Invariants (audit defects B2, B3, B4):
- Version numbers only ever grow; numbers of deleted versions are never reused.
- Versions are never hard-deleted, and a document always keeps at least one live version.
- Writers to the same document are serialized by a row lock on the document.
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, GoneError, NotFoundError
from app.db.models import (
    Document,
    DocumentVersion,
    NotificationKind,
    User,
    VersionSource,
    utcnow,
)
from app.services.activity import record
from app.services.notifications import notify, other_member_ids
from app.utils.diff import build_unified_diff, diff_documents, has_meaningful_changes


@dataclass(frozen=True)
class VersionCreateResult:
    version: DocumentVersion | None  # None when the content was identical
    meaningful: bool  # True when the change should notify people

    @property
    def message(self) -> str:
        return "Version created" if self.version else "No changes detected"


def build_version(
    *,
    document_id: int,
    number: int,
    content: str,
    user: User,
    change_note: str | None = None,
    source: VersionSource = VersionSource.MANUAL,
    restored_from: int | None = None,
    source_filename: str | None = None,
) -> DocumentVersion:
    return DocumentVersion(
        document_id=document_id,
        version_number=number,
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        word_count=len(content.split()),
        change_note=change_note or None,
        source=source.value,
        restored_from=restored_from,
        source_filename=source_filename,
        edited_by=user.id,
    )


def _lock_document(db: Session, document_id: int) -> None:
    """SELECT ... FOR UPDATE on the document row (no-op on SQLite, which serializes writes)."""
    db.execute(select(Document.id).where(Document.id == document_id).with_for_update())


def _live(stmt):  # type: ignore[no-untyped-def]
    return stmt.where(DocumentVersion.deleted_at.is_(None))


def get_version(
    db: Session, document_id: int, version_number: int, *, allow_deleted: bool = False
) -> DocumentVersion:
    version = db.scalar(
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.editor))
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
    )
    if version is None:
        raise NotFoundError(f"Version {version_number} of document {document_id} was not found.")
    if version.is_deleted and not allow_deleted:
        raise GoneError(f"Version {version_number} was deleted.")
    return version


def get_latest_version(db: Session, document_id: int) -> DocumentVersion | None:
    """The newest version that hasn't been deleted."""
    return db.scalar(
        _live(select(DocumentVersion))
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )


def count_live_versions(db: Session, document_id: int) -> int:
    stmt = _live(select(func.count(DocumentVersion.id))).where(
        DocumentVersion.document_id == document_id
    )
    return db.scalar(stmt) or 0


def _next_number(db: Session, document_id: int) -> int:
    # Includes deleted versions, so a deleted number is never handed out again (B2).
    highest = db.scalar(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
    )
    return (highest or 0) + 1


def list_versions(
    db: Session, document: Document, *, include_deleted: bool = False
) -> list[DocumentVersion]:
    stmt = (
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.editor))
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.asc())
    )
    if not include_deleted:
        stmt = _live(stmt)
    return list(db.scalars(stmt))


def create_version(
    db: Session,
    document: Document,
    *,
    content: str,
    user: User,
    change_note: str | None = None,
    source: VersionSource = VersionSource.MANUAL,
    restored_from: int | None = None,
    source_filename: str | None = None,
) -> VersionCreateResult:
    _lock_document(db, document.id)  # held until commit; concurrent writers queue here (B4)

    latest = get_latest_version(db, document.id)
    if latest is not None and latest.content == content:
        db.rollback()  # release the lock
        return VersionCreateResult(version=None, meaningful=False)

    version = build_version(
        document_id=document.id,
        number=_next_number(db, document.id),
        content=content,
        user=user,
        change_note=change_note,
        source=source,
        restored_from=restored_from,
        source_filename=source_filename,
    )
    meaningful = latest is None or has_meaningful_changes(latest.content, content)
    db.add(version)
    document.updated_at = utcnow()
    record(
        db,
        document_id=document.id,
        actor=user,
        action="version.restored" if source == VersionSource.RESTORE else "version.created",
        version=version.version_number,
        source=source.value,
        change_note=version.change_note,
        restored_from=restored_from,
        source_filename=source_filename,
        meaningful=meaningful,
    )
    if meaningful:  # whitespace-only edits don't notify anyone
        notify(
            db,
            user_ids=other_member_ids(db, document.id, user),
            kind=NotificationKind.VERSION_CREATED,
            message=f"{user.name} saved version {version.version_number} of “{document.title}”.",
            actor=user,
            document=document,
            version_number=version.version_number,
        )
    try:
        db.commit()  # the version, its activity event and notifications together
    except IntegrityError as exc:  # only reachable without row locks (SQLite)
        db.rollback()
        raise ConflictError(
            "Another edit to this document was saved at the same moment. Reload and try again."
        ) from exc
    return VersionCreateResult(version=version, meaningful=meaningful)


def restore_version(
    db: Session, document: Document, *, version_number: int, user: User, change_note: str | None
) -> VersionCreateResult:
    """Create a new version whose content is a copy of an earlier one."""
    source = get_version(db, document.id, version_number)
    return create_version(
        db,
        document,
        content=source.content,
        user=user,
        change_note=change_note or f"Restored from version {version_number}",
        source=VersionSource.RESTORE,
        restored_from=version_number,
    )


def delete_version(db: Session, document: Document, *, version_number: int, user: User) -> None:
    """Soft-delete: the version is hidden but kept for the audit trail."""
    _lock_document(db, document.id)
    version = get_version(db, document.id, version_number, allow_deleted=True)
    if version.is_deleted:
        raise GoneError(f"Version {version_number} was already deleted.")
    if count_live_versions(db, document.id) <= 1:
        raise ConflictError("A document must keep at least one version.")  # B3

    version.deleted_at = utcnow()
    version.deleted_by = user.id
    document.updated_at = version.deleted_at
    record(
        db, document_id=document.id, actor=user, action="version.deleted", version=version_number
    )
    db.commit()


def compare_versions(
    db: Session, document: Document, *, v1: int, v2: int, context: int | None = None
) -> dict[str, object]:
    first = get_version(db, document.id, v1)
    second = get_version(db, document.id, v2)
    diff = diff_documents(first.content, second.content, context=context)
    return {
        "document_id": document.id,
        "version_1": v1,
        "version_2": v2,
        "version_1_meta": first,
        "version_2_meta": second,
        "has_meaningful_changes": has_meaningful_changes(first.content, second.content),
        "stats": diff.stats,
        "rows": diff.rows,
        "before": first.content,
        "after": second.content,
        "changes": build_unified_diff(first.content, second.content),
    }
