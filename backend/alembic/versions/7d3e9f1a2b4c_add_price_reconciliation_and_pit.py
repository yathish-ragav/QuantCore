"""add market price reconciliation and point-in-time revisions

Revision ID: 7d3e9f1a2b4c
Revises: 6a1b2c3d4e5f
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d3e9f1a2b4c"
down_revision: Union[str, Sequence[str], None] = "6a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRICE_BASIS = sa.Enum(
    "UNADJUSTED",
    "ADJUSTED",
    name="price_basis",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

DATA_SOURCE = sa.Enum(
    "SEC",
    "FMP",
    "YAHOO",
    "FRED",
    name="data_source",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


def upgrade() -> None:
    """Create immutable price revisions and backfill current observations."""
    op.create_table(
        "price_observation_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("price_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("adjusted_close", sa.Float(), nullable=True),
        sa.Column("price_basis", PRICE_BASIS, nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("dividends", sa.Float(), nullable=False),
        sa.Column("stock_splits", sa.Float(), nullable=False),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["price_id"],
            ["prices.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "price_id",
            "revision_number",
            name="uq_price_observation_revision_price_revision",
        ),
    )

    op.create_index(
        op.f("ix_price_observation_revisions_price_id"),
        "price_observation_revisions",
        ["price_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_price_observation_revisions_known_at"),
        "price_observation_revisions",
        ["known_at"],
        unique=False,
    )

    # Existing Price rows represent the latest known observation at migration
    # time. Preserve them as revision 1 so PIT queries remain usable after the
    # migration without inventing historical revisions.
    op.execute(
        sa.text(
            """
            INSERT INTO price_observation_revisions (
                price_id,
                revision_number,
                date,
                open,
                high,
                low,
                close,
                adjusted_close,
                price_basis,
                volume,
                dividends,
                stock_splits,
                source,
                known_at,
                source_reference
            )
            SELECT
                id,
                1,
                date,
                open,
                high,
                low,
                close,
                adjusted_close,
                price_basis,
                volume,
                dividends,
                stock_splits,
                source,
                COALESCE(fetched_at, CURRENT_TIMESTAMP),
                source_reference
            FROM prices
            """
        )
    )


def downgrade() -> None:
    """Remove immutable price revision history."""
    op.drop_index(
        op.f("ix_price_observation_revisions_known_at"),
        table_name="price_observation_revisions",
    )
    op.drop_index(
        op.f("ix_price_observation_revisions_price_id"),
        table_name="price_observation_revisions",
    )
    op.drop_table("price_observation_revisions")
