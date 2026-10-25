"""price asset prices until

Revision ID: a1c3e5f70b21
Revises: 907df0a86dca
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f70b21"
down_revision: str | None = "907df0a86dca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("price_asset", sa.Column("prices_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("price_asset", "prices_until")
