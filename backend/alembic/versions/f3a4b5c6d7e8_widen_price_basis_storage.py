"""Widen price basis storage.

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-15 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen price-basis columns to store the canonical enum values."""
    for table_name in ("prices", "price_observation_revisions"):
        op.alter_column(
            table_name,
            "price_basis",
            existing_type=sa.VARCHAR(length=5),
            type_=sa.VARCHAR(length=10),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Restore the legacy five-character storage width."""
    for table_name in ("prices", "price_observation_revisions"):
        op.alter_column(
            table_name,
            "price_basis",
            existing_type=sa.VARCHAR(length=10),
            type_=sa.VARCHAR(length=5),
            existing_nullable=False,
        )
