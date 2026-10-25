"""manual entries: raw_retraction (ADR 0036)

Revision ID: d4e5f6a7b8c9
Revises: c39161c4c1a9
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c39161c4c1a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_retraction",
        sa.Column("raw_id", sa.BigInteger(), nullable=False),
        sa.Column("replaced_by_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["raw_id"], ["raw_transaction.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["raw_transaction.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("raw_id"),
    )


def downgrade() -> None:
    op.drop_table("raw_retraction")
