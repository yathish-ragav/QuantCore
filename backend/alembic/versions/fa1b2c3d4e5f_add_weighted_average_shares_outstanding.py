"""separate shares outstanding from weighted-average shares

Revision ID: fa1b2c3d4e5f
Revises: fa0b1c2d3e4f
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fa1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "fa0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store true period-end shares separately from weighted-average shares."""
    op.add_column(
        "income_statements",
        sa.Column("weighted_average_shares_outstanding", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "financial_statement_revisions",
        sa.Column("weighted_average_shares_outstanding", sa.BigInteger(), nullable=True),
    )

    # Before this migration, QuantCore's canonical shares_outstanding field
    # contained weighted-average shares for the financial providers. Preserve
    # those historical values under their correct semantic name, then clear the
    # mislabeled field so subsequent ingestion can populate true shares.
    op.execute(
        sa.text(
            "UPDATE income_statements "
            "SET weighted_average_shares_outstanding = shares_outstanding, "
            "shares_outstanding = NULL "
            "WHERE shares_outstanding IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE financial_statement_revisions "
            "SET weighted_average_shares_outstanding = shares_outstanding, "
            "shares_outstanding = NULL "
            "WHERE shares_outstanding IS NOT NULL"
        )
    )


def downgrade() -> None:
    """Restore the legacy single shares field using weighted-average values."""
    op.execute(
        sa.text(
            "UPDATE income_statements "
            "SET shares_outstanding = weighted_average_shares_outstanding "
            "WHERE shares_outstanding IS NULL "
            "AND weighted_average_shares_outstanding IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE financial_statement_revisions "
            "SET shares_outstanding = weighted_average_shares_outstanding "
            "WHERE shares_outstanding IS NULL "
            "AND weighted_average_shares_outstanding IS NOT NULL"
        )
    )
    op.drop_column("financial_statement_revisions", "weighted_average_shares_outstanding")
    op.drop_column("income_statements", "weighted_average_shares_outstanding")
