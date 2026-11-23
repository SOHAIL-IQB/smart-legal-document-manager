"""activity log and notifications

Adds the append-only activity_events table and the notifications inbox, and backfills
activity from existing history: one document.created per document, one version event per
version (with its editor and time) and a version.deleted for each soft-deleted version.

Revision ID: 20261123_0006
Revises: 20261122_0005
Create Date: 2026-11-23 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261123_0006"
down_revision = "20261122_0005"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
KINDS = ("version_created", "document_shared", "role_changed", "removed_from_document", "document_deleted")


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("details", JSON, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_activity_events_document_created", "activity_events", ["document_id", "created_at"]
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="SET NULL")
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("version_number", sa.Integer()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN (" + ", ".join(f"'{k}'" for k in KINDS) + ")", name="ck_notification_kind"
        ),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read_at"])

    _backfill_activity()


def _backfill_activity() -> None:
    connection = op.get_bind()
    documents = sa.table(
        "documents",
        sa.column("id", sa.Integer),
        sa.column("title", sa.String),
        sa.column("created_by", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    versions = sa.table(
        "document_versions",
        sa.column("document_id", sa.Integer),
        sa.column("version_number", sa.Integer),
        sa.column("source", sa.String),
        sa.column("change_note", sa.String),
        sa.column("restored_from", sa.Integer),
        sa.column("source_filename", sa.String),
        sa.column("edited_by", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
        sa.column("deleted_by", sa.Integer),
    )
    events = sa.table(
        "activity_events",
        sa.column("document_id", sa.Integer),
        sa.column("actor_id", sa.Integer),
        sa.column("action", sa.String),
        sa.column("details", JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    def clean(**details):  # same rule as app.services.activity.record: drop None values
        return {key: value for key, value in details.items() if value is not None}

    rows = []
    first_versions = {}
    for v in connection.execute(sa.select(versions).order_by(versions.c.version_number)):
        first_versions.setdefault(v.document_id, v)
        if v.version_number > 1:
            rows.append(
                {
                    "document_id": v.document_id,
                    "actor_id": v.edited_by,
                    "action": "version.restored" if v.source == "restore" else "version.created",
                    "details": clean(
                        version=v.version_number,
                        source=v.source,
                        change_note=v.change_note,
                        restored_from=v.restored_from,
                        source_filename=v.source_filename,
                        backfilled=True,
                    ),
                    "created_at": v.created_at,
                }
            )
        if v.deleted_at is not None:
            rows.append(
                {
                    "document_id": v.document_id,
                    "actor_id": v.deleted_by or v.edited_by,
                    "action": "version.deleted",
                    "details": {"version": v.version_number, "backfilled": True},
                    "created_at": v.deleted_at,
                }
            )
    for d in connection.execute(sa.select(documents)):
        first = first_versions.get(d.id)
        rows.append(
            {
                "document_id": d.id,
                "actor_id": d.created_by,
                "action": "document.created",
                "details": clean(
                    title=d.title,
                    version=1,
                    source=first.source if first else None,
                    source_filename=first.source_filename if first else None,
                    backfilled=True,
                ),
                "created_at": d.created_at,
            }
        )
    if rows:
        op.bulk_insert(events, rows)


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_activity_events_document_created", table_name="activity_events")
    op.drop_table("activity_events")
