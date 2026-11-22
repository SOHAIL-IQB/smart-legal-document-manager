from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import Document, DocumentVersion
from app.services.users import get_user


def get_document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} was not found.")
    return document


def list_documents(db: Session) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc(), Document.id.desc())
    return list(db.scalars(stmt))


def create_document(
    db: Session, *, title: str, content: str, user_id: int
) -> tuple[Document, DocumentVersion]:
    get_user(db, user_id)

    document = Document(title=title, created_by=user_id)
    db.add(document)
    db.flush()  # assigns document.id

    version = DocumentVersion(
        document_id=document.id, version_number=1, content=content, edited_by=user_id
    )
    db.add(version)
    db.commit()
    return document, version


def rename_document(db: Session, *, document_id: int, title: str) -> Document:
    document = get_document(db, document_id)
    document.title = title
    db.commit()
    return document


def delete_document(db: Session, *, document_id: int) -> None:
    db.delete(get_document(db, document_id))
    db.commit()


def count_versions(db: Session, document_id: int) -> int:
    stmt = select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document_id)
    return db.scalar(stmt) or 0
