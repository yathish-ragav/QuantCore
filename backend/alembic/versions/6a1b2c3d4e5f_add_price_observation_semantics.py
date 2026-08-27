"""add market price observation semantics

Revision ID: 6a1b2c3d4e5f
Revises: f7a8b9c0d1e2
Create Date: 2026-08-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
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


def upgrade() -> None:
    """Add explicit price-field adjustment semantics."""
    op.add_column(
        "prices",
        sa.Column(
            "adjusted_close",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "prices",
        sa.Column(
            "price_basis",
            PRICE_BASIS,
            nullable=False,
            server_default="UNADJUSTED",
        ),
    )
    op.alter_column(
        "prices",
        "price_basis",
        server_default=None,
    )
    op.create_index(
        op.f("ix_prices_price_basis"),
        "prices",
        ["price_basis"],
        unique=False,
    )


def downgrade() -> None:
    """Remove explicit price-field adjustment semantics."""
    op.drop_index(
        op.f("ix_prices_price_basis"),
        table_name="prices",
    )
    op.drop_column("prices", "price_basis")
    op.drop_column("prices", "adjusted_close")
