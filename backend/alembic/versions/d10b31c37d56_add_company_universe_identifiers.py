"""add company universe identifiers

Revision ID: d10b31c37d56
Revises: be5f4b0bfae2
Create Date: 2026-08-13 13:06:59.115229

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd10b31c37d56'
down_revision: Union[str, Sequence[str], None] = 'be5f4b0bfae2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "companies",
        sa.Column(
            "cik",
            sa.String(length=10),
            nullable=True,
        ),
    )

    op.add_column(
        "companies",
        sa.Column(
            "exchange",
            sa.String(length=50),
            nullable=True,
        ),
    )

    # Backfill the existing development record.
    op.execute(
        """
        UPDATE companies
        SET
            cik = '0000320193',
            exchange = 'NASDAQ'
        WHERE symbol = 'AAPL'
        """
    )

    op.alter_column(
        "companies",
        "cik",
        existing_type=sa.String(length=10),
        nullable=False,
    )

    op.alter_column(
        "companies",
        "exchange",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    op.create_index(
        op.f("ix_companies_cik"),
        "companies",
        ["cik"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_companies_cik"),
        table_name="companies",
    )

    op.drop_column(
        "companies",
        "exchange",
    )

    op.drop_column(
        "companies",
        "cik",
    )