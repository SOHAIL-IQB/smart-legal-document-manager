from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.db.models import Document, DocumentMember, DocumentVersion, Role, User


@dataclass(frozen=True)
class DocumentAccess:
    document: Document
    user: User
    role: Role


def _not_found(document_id: int) -> NotFoundError:
    return NotFoundError(f"Document {document_id} was not found.")


def get_document_access(
    db: Session, *, document_id: int, user: User, minimum: Role
) -> DocumentAccess:
    """Resolve the caller's role on a document.

    Non-members get the same 404 as a missing document, so ids can't be probed.
    Members without enough rights get 403.
    """
    row = db.execute(
        select(Document, DocumentMember.role)
        .join(DocumentMember, DocumentMember.document_id == Document.id)
        .where(Document.id == document_id, DocumentMember.user_id == user.id)
    ).first()
    if row is None:
        raise _not_found(document_id)

    document, role_value = row
    role = Role(role_value)
    if not role.allows(minimum):
        raise PermissionDeniedError(
            f"This action needs the {minimum.value} role; your role is {role.value}."
        )
    return DocumentAccess(document=document, user=user, role=role)


def list_documents_for_user(db: Session, user: User) -> list[tuple[Document, Role]]:
    rows = db.execute(
        select(Document, DocumentMember.role)
        .join(DocumentMember, DocumentMember.document_id == Document.id)
        .where(DocumentMember.user_id == user.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    return [(document, Role(role)) for document, role in rows]


def create_document(
    db: Session, *, title: str, content: str, user: User
) -> tuple[Document, DocumentVersion]:
    document = Document(title=title, created_by=user.id)
    db.add(document)
    db.flush()  # assigns document.id

    db.add(DocumentMember(document_id=document.id, user_id=user.id, role=Role.OWNER.value))
    version = DocumentVersion(
        document_id=document.id, version_number=1, content=content, edited_by=user.id
    )
    db.add(version)
    db.commit()
    db.refresh(document)
    return document, version


def rename_document(db: Session, document: Document, *, title: str) -> Document:
    document.title = title
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()


def count_versions(db: Session, document_id: int) -> int:
    stmt = select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document_id)
    return db.scalar(stmt) or 0
