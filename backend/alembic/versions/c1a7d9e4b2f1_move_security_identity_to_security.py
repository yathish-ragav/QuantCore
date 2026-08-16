"""move market identity from company to security

Revision ID: c1a7d9e4b2f1
Revises: 7642e3454034
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a7d9e4b2f1"
down_revision: Union[str, Sequence[str], None] = "7642e3454034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make Company issuer-only and Security market-identity owner."""

    connection = op.get_bind()

    # Every company must already have a security before symbol/exchange
    # are removed from companies. This prevents silent loss of market
    # identity during the migration.
    missing_securities = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM companies AS c
            WHERE NOT EXISTS (
                SELECT 1
                FROM securities AS s
                WHERE s.company_id = c.id
            )
            """
        )
    ).scalar_one()

    if missing_securities != 0:
        raise RuntimeError(
            "Migration aborted: "
            f"{missing_securities} companies have no security."
        )

    # Symbol is currently the public security identifier throughout
    # QuantCore. Enforce that invariant before removing the duplicate
    # company-level symbol.
    duplicate_symbols = connection.execute(
        sa.text(
            """
            SELECT symbol
            FROM securities
            GROUP BY symbol
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()

    if duplicate_symbols is not None:
        raise RuntimeError(
            "Migration aborted: duplicate security symbols exist. "
            "Resolve them before moving symbol ownership to Security."
        )

    op.drop_constraint(
        "uq_security_company_symbol",
        "securities",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_security_symbol",
        "securities",
        ["symbol"],
    )

    op.drop_index(
        "ix_companies_symbol",
        table_name="companies",
    )

    op.drop_column("companies", "symbol")
    op.drop_column("companies", "exchange")


def downgrade() -> None:
    """Restore Company symbol/exchange as a compatibility projection."""

    op.add_column(
        "companies",
        sa.Column(
            "symbol",
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

    # A Company may have multiple Securities. For downgrade only, use
    # the lowest security id as the deterministic representative.
    op.execute(
        sa.text(
            """
            UPDATE companies AS c
            SET
                symbol = s.symbol,
                exchange = s.exchange
            FROM (
                SELECT DISTINCT ON (company_id)
                    company_id,
                    symbol,
                    exchange
                FROM securities
                ORDER BY company_id, id
            ) AS s
            WHERE c.id = s.company_id
            """
        )
    )

    connection = op.get_bind()
    missing_identity = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM companies
            WHERE symbol IS NULL
               OR exchange IS NULL
            """
        )
    ).scalar_one()

    if missing_identity != 0:
        raise RuntimeError(
            "Downgrade aborted: "
            f"{missing_identity} companies could not be assigned "
            "a representative security."
        )

    op.alter_column(
        "companies",
        "symbol",
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
        "ix_companies_symbol",
        "companies",
        ["symbol"],
        unique=True,
    )

    op.drop_constraint(
        "uq_security_symbol",
        "securities",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_security_company_symbol",
        "securities",
        ["company_id", "symbol"],
    )
