from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import NotFoundError, PermissionDeniedError
from app.db.models import Document, DocumentMember, DocumentVersion, Role, User
from app.services.versions import build_version


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


SortField = Literal["updated_at", "created_at", "title"]
SortOrder = Literal["asc", "desc"]


@dataclass(frozen=True)
class DocumentSummary:
    document: Document
    role: Role
    created_by_name: str
    latest_version: int | None
    version_count: int
    word_count: int | None


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _summaries_for(user: User):  # type: ignore[no-untyped-def]
    """One row per document the user belongs to, with live-version stats and latest content."""
    stats = (
        select(
            DocumentVersion.document_id.label("document_id"),
            func.max(DocumentVersion.version_number).label("latest"),
            func.count(DocumentVersion.id).label("live_count"),
        )
        .where(DocumentVersion.deleted_at.is_(None))
        .group_by(DocumentVersion.document_id)
        .subquery()
    )
    latest = aliased(DocumentVersion)
    creator = aliased(User)
    stmt = (
        select(
            Document,
            DocumentMember.role,
            creator.name,
            stats.c.latest,
            stats.c.live_count,
            latest.word_count,
        )
        .join(
            DocumentMember,
            and_(DocumentMember.document_id == Document.id, DocumentMember.user_id == user.id),
        )
        .join(creator, creator.id == Document.created_by)
        .outerjoin(stats, stats.c.document_id == Document.id)
        .outerjoin(
            latest,
            and_(latest.document_id == Document.id, latest.version_number == stats.c.latest),
        )
    )
    return stmt, latest


def _to_summary(row) -> DocumentSummary:  # type: ignore[no-untyped-def]
    document, role, creator_name, latest_version, live_count, word_count = row
    return DocumentSummary(
        document=document,
        role=Role(role),
        created_by_name=creator_name,
        latest_version=latest_version,
        version_count=live_count or 0,
        word_count=word_count,
    )


def search_documents(
    db: Session,
    user: User,
    *,
    query: str | None = None,
    role: Role | None = None,
    sort: SortField = "updated_at",
    order: SortOrder = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DocumentSummary], int]:
    """Documents the user belongs to, filtered and paginated. Returns (page, total)."""
    stmt, latest = _summaries_for(user)
    if query and query.strip():
        pattern = f"%{_escape_like(query.strip())}%"
        stmt = stmt.where(
            or_(
                Document.title.ilike(pattern, escape="\\"),
                latest.content.ilike(pattern, escape="\\"),
            )
        )
    if role is not None:
        stmt = stmt.where(DocumentMember.role == role.value)

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0

    column = {
        "updated_at": Document.updated_at,
        "created_at": Document.created_at,
        "title": func.lower(Document.title),
    }[sort]
    direction = column.asc() if order == "asc" else column.desc()
    tiebreak = Document.id.asc() if order == "asc" else Document.id.desc()
    rows = db.execute(stmt.order_by(direction, tiebreak).limit(limit).offset(offset)).all()
    return [_to_summary(row) for row in rows], total


def get_document_summary(db: Session, access: DocumentAccess) -> DocumentSummary:
    stmt, _ = _summaries_for(access.user)
    return _to_summary(db.execute(stmt.where(Document.id == access.document.id)).one())


def create_document(
    db: Session, *, title: str, content: str, user: User
) -> tuple[Document, DocumentVersion]:
    document = Document(title=title, created_by=user.id)
    db.add(document)
    db.flush()  # assigns document.id

    db.add(DocumentMember(document_id=document.id, user_id=user.id, role=Role.OWNER.value))
    version = build_version(document_id=document.id, number=1, content=content, user=user)
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
