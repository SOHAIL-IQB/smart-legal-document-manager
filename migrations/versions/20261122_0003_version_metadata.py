"""version metadata and soft delete

Adds content_hash, word_count, change_note, source, restored_from, deleted_at and
deleted_by to document_versions, and backfills hash and word count for existing rows.

Revision ID: 20261122_0003
Revises: 20261122_0002
Create Date: 2026-11-22 00:00:00
"""

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "20261122_0003"
down_revision = "20261122_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("document_versions") as batch:
        batch.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("word_count", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("change_note", sa.String(500), nullable=True))
        batch.add_column(
            sa.Column("source", sa.String(16), nullable=False, server_default="manual")
        )
        batch.add_column(sa.Column("restored_from", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "deleted_by",
                sa.Integer(),
                sa.ForeignKey("users.id", name="fk_document_versions_deleted_by"),
                nullable=True,
            )
        )

    connection = op.get_bind()
    versions = sa.table(
        "document_versions",
        sa.column("id", sa.Integer),
        sa.column("content", sa.Text),
        sa.column("content_hash", sa.String),
        sa.column("word_count", sa.Integer),
    )
    for row in connection.execute(sa.select(versions.c.id, versions.c.content)):
        connection.execute(
            versions.update()
            .where(versions.c.id == row.id)
            .values(
                content_hash=hashlib.sha256(row.content.encode("utf-8")).hexdigest(),
                word_count=len(row.content.split()),
            )
        )

    with op.batch_alter_table("document_versions") as batch:
        batch.alter_column("content_hash", existing_type=sa.String(64), nullable=False)
        batch.alter_column("word_count", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("source", existing_type=sa.String(16), server_default=None)
        batch.create_check_constraint(
            "ck_document_version_source", "source IN ('manual', 'restore', 'upload')"
        )


def downgrade() -> None:
    with op.batch_alter_table("document_versions") as batch:
        batch.drop_constraint("ck_document_version_source", type_="check")
        batch.drop_constraint("fk_document_versions_deleted_by", type_="foreignkey")
        for column in (
            "deleted_by",
            "deleted_at",
            "restored_from",
            "source",
            "change_note",
            "word_count",
            "content_hash",
        ):
            batch.drop_column(column)
