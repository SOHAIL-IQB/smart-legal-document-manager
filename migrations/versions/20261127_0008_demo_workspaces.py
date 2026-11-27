"""demo workspaces

Adds demo_workspaces and users.demo_workspace_id for the private demo workspace per visitor
(Phase 9 F1, spec docs/specs/phase-9-frontend-build.md). Additive: real accounts keep a NULL
demo_workspace_id. No visitor data is stored.

Revision ID: 20261127_0008
Revises: 20261124_0007
Create Date: 2026-11-27 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20261127_0008"
down_revision = "20261124_0007"
branch_labels = None
depends_on = None

FK_NAME = "fk_users_demo_workspace_id_demo_workspaces"


def upgrade() -> None:
    op.create_table(
        "demo_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_demo_workspaces_expires_at", "demo_workspaces", ["expires_at"])
    with op.batch_alter_table("users") as batch:  # batch: SQLite can't add a foreign key otherwise
        batch.add_column(sa.Column("demo_workspace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(FK_NAME, "demo_workspaces", ["demo_workspace_id"], ["id"])
        batch.create_index("ix_users_demo_workspace_id", ["demo_workspace_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_demo_workspace_id")
        batch.drop_constraint(FK_NAME, type_="foreignkey")
        batch.drop_column("demo_workspace_id")
    op.drop_index("ix_demo_workspaces_expires_at", table_name="demo_workspaces")
    op.drop_table("demo_workspaces")
