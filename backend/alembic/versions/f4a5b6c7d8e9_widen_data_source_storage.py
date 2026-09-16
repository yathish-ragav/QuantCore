"""Widen data source storage.

Revision ID: f4a5b6c7d8e9
Revises: f3a4b5c6d7e8
Create Date: 2026-09-16 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen provenance source columns for canonical provider identifiers."""
    for table_name in ("prices", "price_observation_revisions"):
        op.alter_column(
            table_name,
            "source",
            existing_type=sa.VARCHAR(length=5),
            type_=sa.VARCHAR(length=10),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Restore the legacy five-character source storage width."""
    for table_name in ("prices", "price_observation_revisions"):
        op.alter_column(
            table_name,
            "source",
            existing_type=sa.VARCHAR(length=10),
            type_=sa.VARCHAR(length=5),
            existing_nullable=False,
        )
