"""mcp change

Revision ID: e7a2c9d4b1f6
Revises: d5f1b3a7c2e8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a2c9d4b1f6"
down_revision: str | None = "d5f1b3a7c2e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_change",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("token", sa.String(length=80), nullable=False),
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("item", sa.JSON(), nullable=False),
        sa.Column("row_ids", sa.JSON(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_change_plan_id", "mcp_change", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_change_plan_id", table_name="mcp_change")
    op.drop_table("mcp_change")
