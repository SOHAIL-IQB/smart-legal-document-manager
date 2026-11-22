import enum
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    """The one clock for every timestamp the app writes (microsecond precision on any database).

    `server_default=func.now()` stays on the columns only for rows inserted with raw SQL.
    """
    return datetime.now(UTC)


class Role(enum.StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def allows(self, required: "Role") -> bool:
        return self.rank >= required.rank


_ROLE_RANK = {Role.VIEWER: 1, Role.EDITOR: 2, Role.OWNER: 3}


class VersionSource(enum.StrEnum):
    MANUAL = "manual"  # typed or pasted
    RESTORE = "restore"  # copied from an earlier version
    UPLOAD = "upload"  # extracted from a file (Phase 5)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    created_documents: Mapped[list["Document"]] = relationship(back_populates="creator")
    edited_versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="editor", foreign_keys="DocumentVersion.edited_by"
    )
    memberships: Mapped[list["DocumentMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    creator: Mapped["User"] = relationship(back_populates="created_documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
    )
    members: Mapped[list["DocumentMember"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentMember(Base):
    __tablename__ = "document_members"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="ck_document_member_role"),
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),
        CheckConstraint(
            "source IN ('manual', 'restore', 'upload')", name="ck_document_version_source"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=VersionSource.MANUAL)
    restored_from: Mapped[int | None] = mapped_column(Integer)  # version number it restores
    source_filename: Mapped[str | None] = mapped_column(String(255))  # uploads only
    edited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    # Versions are never hard-deleted (audit trail); "delete" hides them.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    document: Mapped["Document"] = relationship(back_populates="versions")
    editor: Mapped["User"] = relationship(
        back_populates="edited_versions", foreign_keys=[edited_by]
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def edited_by_name(self) -> str:
        return self.editor.name
