from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.database.models import Document, DocumentVersion, User


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} was not found.")
    return user


def get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} was not found.")
    return document


def get_version_or_404(db: Session, document_id: int, version_number: int) -> DocumentVersion:
    stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == version_number,
    )
    version = db.scalar(stmt)
    if version is None:
        raise ValueError(
            f"Version {version_number} for document {document_id} was not found."
        )
    return version


def get_latest_version(db: Session, document_id: int) -> DocumentVersion | None:
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def count_versions(db: Session, document_id: int) -> int:
    stmt = select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document_id)
    return db.scalar(stmt) or 0


def list_documents_stmt() -> Select[tuple[Document]]:
    return select(Document).order_by(Document.created_at.desc(), Document.id.desc())


def list_versions_stmt(document_id: int) -> Select[tuple[DocumentVersion]]:
    return (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.asc())
    )
