"""user deleted_at

Adds users.deleted_at for account deletion (Phase 7 T15). A deleted account is anonymized
rather than removed, because documents, versions and the append-only activity log refer to it;
this column marks it so its unexpired tokens are refused.

Revision ID: 20261124_0007
Revises: 20261123_0006
Create Date: 2026-11-24 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0007"
down_revision = "20261123_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:  # batch: SQLite can't drop columns otherwise
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("deleted_at")
