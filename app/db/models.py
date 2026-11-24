import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db.session import Base


class UTCDateTime(TypeDecorator[datetime]):
    """Timestamps are always timezone-aware UTC when they leave the database.

    Postgres `timestamptz` already does this; SQLite returns naive values, which the API would
    serialize without a zone and browsers would read as local time. Found in Phase 6 (LOG 012).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Store timezone-aware datetimes only (use utcnow()).")
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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


class NotificationKind(enum.StrEnum):
    VERSION_CREATED = "version_created"
    DOCUMENT_SHARED = "document_shared"
    ROLE_CHANGED = "role_changed"
    REMOVED_FROM_DOCUMENT = "removed_from_document"
    DOCUMENT_DELETED = "document_deleted"


def _in_list(column: str, values: type[enum.StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
    )
    # Set when the account is deleted: the row stays as an anonymous placeholder so history
    # (versions, activity) still resolves, and its tokens stop working (Phase 7 T15).
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

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
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    creator: Mapped["User"] = relationship(back_populates="created_documents")
    # passive_deletes: the database's ON DELETE CASCADE removes children, so deleting a
    # document doesn't load every version's content first (review finding R2).
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentVersion.version_number",
    )
    members: Mapped[list["DocumentMember"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
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
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
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
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
    )
    # Versions are never hard-deleted (audit trail); "delete" hides them.
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
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


_JSON = JSON().with_variant(JSONB(), "postgresql")


class ActivityEvent(Base):
    """Append-only audit trail of everything that happened to a document.

    Written in the same transaction as the action it describes. Rows can't be updated or
    deleted through the ORM (see the listeners below); they go only when their document does.
    """

    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_events_document_created", "document_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
    )

    actor: Mapped["User"] = relationship()


@event.listens_for(ActivityEvent, "before_update")
@event.listens_for(ActivityEvent, "before_delete")
def _activity_is_append_only(*_args: object) -> None:
    raise PermissionError("Activity events are append-only.")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(_in_list("kind", NotificationKind), name="ck_notification_kind"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # SET NULL: "Alice deleted “NDA”" must outlive the document it talks about.
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    version_number: Mapped[int | None] = mapped_column(Integer)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])
