"""version source filename

Records the original file name of versions created by upload.

Revision ID: 20261122_0004
Revises: 20261122_0003
Create Date: 2026-11-22 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0004"
down_revision = "20261122_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("document_versions") as batch:
        batch.add_column(sa.Column("source_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("document_versions") as batch:
        batch.drop_column("source_filename")
