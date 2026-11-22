"""cascade version delete

Deleting a document now removes its versions in the database (ON DELETE CASCADE) instead of
the application loading and deleting each one (review finding R2).

Revision ID: 20261122_0005
Revises: 20261122_0004
Create Date: 2026-11-22 00:00:00
"""

from alembic import op

revision = "20261122_0005"
down_revision = "20261122_0004"
branch_labels = None
depends_on = None

POSTGRES_NAME = "document_versions_document_id_fkey"  # name Postgres gave the unnamed FK in 0001
# SQLite keeps no constraint names; this convention lets batch mode find the reflected FK.
SQLITE_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
SQLITE_NAME = "fk_document_versions_document_id_documents"


def _replace_fk(ondelete: str | None) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "document_versions", naming_convention=SQLITE_CONVENTION
        ) as batch:
            batch.drop_constraint(SQLITE_NAME, type_="foreignkey")
            batch.create_foreign_key(
                SQLITE_NAME, "documents", ["document_id"], ["id"], ondelete=ondelete
            )
        return
    op.drop_constraint(POSTGRES_NAME, "document_versions", type_="foreignkey")
    op.create_foreign_key(
        POSTGRES_NAME, "document_versions", "documents", ["document_id"], ["id"], ondelete=ondelete
    )


def upgrade() -> None:
    _replace_fk("CASCADE")


def downgrade() -> None:
    _replace_fk(None)
