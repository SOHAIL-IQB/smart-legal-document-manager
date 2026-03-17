from sqlalchemy.orm import Session

from app.database.models import Document, DocumentVersion
from app.services.document_service import (
    get_document_or_404,
    get_latest_version,
    get_user_or_404,
    get_version_or_404,
)


def create_document_with_initial_version(
    db: Session,
    *,
    title: str,
    content: str,
    user_id: int,
) -> tuple[Document, DocumentVersion]:
    get_user_or_404(db, user_id)

    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        document = Document(title=title, created_by=user_id)
        db.add(document)
        db.flush()

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            content=content,
            edited_by=user_id,
        )
        db.add(version)

    db.refresh(document)
    db.refresh(version)
    return document, version


def create_document_version(
    db: Session,
    *,
    document_id: int,
    content: str,
    user_id: int,
) -> tuple[str, DocumentVersion | None]:
    get_user_or_404(db, user_id)
    get_document_or_404(db, document_id)

    latest_version = get_latest_version(db, document_id)
    if latest_version is None:
        raise ValueError(f"Document {document_id} does not have any versions yet.")
    if latest_version.content == content:
        return "No changes detected", None

    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        version = DocumentVersion(
            document_id=document_id,
            version_number=latest_version.version_number + 1,
            content=content,
            edited_by=user_id,
        )
        db.add(version)

    db.refresh(version)
    return "Version created", version


def update_document_title(db: Session, *, document_id: int, title: str) -> Document:
    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        document = get_document_or_404(db, document_id)
        document.title = title
        db.add(document)

    db.refresh(document)
    return document


def delete_document_version(db: Session, *, document_id: int, version_number: int) -> None:
    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        get_document_or_404(db, document_id)
        version_record = get_version_or_404(db, document_id, version_number)
        db.delete(version_record)


def delete_document(db: Session, *, document_id: int) -> None:
    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        document = get_document_or_404(db, document_id)
        db.delete(document)
