"""rows a source delivered again with other values

Revision ID: a4c7e2f9b315
Revises: f3b8d1e5a9c4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c7e2f9b315"
down_revision: str | None = "f3b8d1e5a9c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_run", sa.Column("changed", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_table(
        "raw_source_change",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "raw_id",
            sa.BigInteger(),
            sa.ForeignKey("raw_transaction.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "import_run_id",
            sa.BigInteger(),
            sa.ForeignKey("import_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("movement", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column(
            "replaced_by_id",
            sa.BigInteger(),
            sa.ForeignKey("raw_transaction.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("raw_id", "fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("raw_source_change")
    op.drop_column("import_run", "changed")
