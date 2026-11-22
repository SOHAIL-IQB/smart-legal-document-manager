"""auth and document members

Adds password hashes and timestamps to users, updated_at to documents, and the
document_members table. Every existing document's creator becomes its owner.

Revision ID: 20261122_0002
Revises: 20260317_0001
Create Date: 2026-11-22 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None

# Not a valid Argon2 hash, so accounts created before this migration cannot log in.
UNUSABLE_HASH = "!unusable"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "password_hash",
                sa.String(length=255),
                nullable=False,
                server_default=UNUSABLE_HASH,
            )
        )
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", server_default=None)

    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
    op.execute("UPDATE documents SET updated_at = created_at")

    op.create_table(
        "document_members",
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="ck_document_member_role"),
    )
    op.create_index(
        op.f("ix_document_members_user_id"), "document_members", ["user_id"], unique=False
    )
    op.execute(
        "INSERT INTO document_members (document_id, user_id, role) "
        "SELECT id, created_by, 'owner' FROM documents"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_members_user_id"), table_name="document_members")
    op.drop_table("document_members")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("updated_at")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("created_at")
        batch.drop_column("password_hash")
