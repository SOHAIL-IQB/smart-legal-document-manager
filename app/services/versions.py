from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.db.models import DocumentVersion, User
from app.services.documents import get_document
from app.services.users import get_user
from app.utils.diff import build_unified_diff, has_meaningful_changes


@dataclass(frozen=True)
class VersionCreateResult:
    version: DocumentVersion | None  # None when the content was identical
    editor: User
    meaningful: bool  # True when the change should notify people

    @property
    def message(self) -> str:
        return "Version created" if self.version else "No changes detected"


def get_version(db: Session, document_id: int, version_number: int) -> DocumentVersion:
    stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == version_number,
    )
    version = db.scalar(stmt)
    if version is None:
        raise NotFoundError(f"Version {version_number} of document {document_id} was not found.")
    return version


def get_latest_version(db: Session, document_id: int) -> DocumentVersion | None:
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def list_versions(db: Session, document_id: int) -> list[DocumentVersion]:
    get_document(db, document_id)
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.asc())
    )
    return list(db.scalars(stmt))


def create_version(
    db: Session, *, document_id: int, content: str, user_id: int
) -> VersionCreateResult:
    editor = get_user(db, user_id)
    get_document(db, document_id)

    latest = get_latest_version(db, document_id)
    if latest is None:
        # Reachable only until Phase 3 forbids deleting a document's last version.
        raise ConflictError(f"Document {document_id} has no versions to build on.")
    if latest.content == content:
        return VersionCreateResult(version=None, editor=editor, meaningful=False)

    version = DocumentVersion(
        document_id=document_id,
        version_number=latest.version_number + 1,
        content=content,
        edited_by=user_id,
    )
    db.add(version)
    db.commit()
    return VersionCreateResult(
        version=version, editor=editor, meaningful=has_meaningful_changes(latest.content, content)
    )


def delete_version(db: Session, *, document_id: int, version_number: int) -> None:
    get_document(db, document_id)
    db.delete(get_version(db, document_id, version_number))
    db.commit()


def compare_versions(db: Session, *, document_id: int, v1: int, v2: int) -> dict[str, object]:
    get_document(db, document_id)
    before = get_version(db, document_id, v1).content
    after = get_version(db, document_id, v2).content
    return {
        "document_id": document_id,
        "version_1": v1,
        "version_2": v2,
        "before": before,
        "after": after,
        "changes": build_unified_diff(before, after),
        "has_meaningful_changes": has_meaningful_changes(before, after),
    }
