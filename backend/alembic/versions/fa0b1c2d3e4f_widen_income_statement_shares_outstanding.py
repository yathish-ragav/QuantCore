"""widen income statement shares outstanding

Revision ID: fa0b1c2d3e4f
Revises: f9a0b1c2d3e4
Create Date: 2026-09-16 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fa0b1c2d3e4f"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen shares outstanding to support large-cap US issuers."""
    op.alter_column(
        "income_statements",
        "shares_outstanding",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Narrow shares outstanding back to INTEGER."""
    op.alter_column(
        "income_statements",
        "shares_outstanding",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
