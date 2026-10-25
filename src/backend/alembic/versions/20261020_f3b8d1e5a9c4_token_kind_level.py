"""token kind and level; mcp.mode becomes mcp.enabled plus a level per token

Revision ID: f3b8d1e5a9c4
Revises: e7a2c9d4b1f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b8d1e5a9c4"
down_revision: str | None = "e7a2c9d4b1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_token", sa.Column("kind", sa.String(length=10), server_default="mcp", nullable=False)
    )
    op.add_column(
        "mcp_token", sa.Column("level", sa.String(length=10), server_default="read", nullable=False)
    )
    # the old switch for all: "edit" goes to every existing token, "read"/"edit" means on
    op.execute("""UPDATE mcp_token SET level = 'edit'
                  WHERE EXISTS (SELECT 1 FROM setting WHERE key = 'mcp.mode' AND value = '"edit"'::jsonb)""")
    op.execute("""INSERT INTO setting (key, value)
                  SELECT 'mcp.enabled', 'true'::jsonb FROM setting
                  WHERE key = 'mcp.mode' AND value IN ('"read"'::jsonb, '"edit"'::jsonb)
                  ON CONFLICT (key) DO NOTHING""")
    op.execute("DELETE FROM setting WHERE key = 'mcp.mode'")


def downgrade() -> None:
    op.drop_column("mcp_token", "level")
    op.drop_column("mcp_token", "kind")
