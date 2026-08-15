"""create initial application schema

Revision ID: 000000000001
Revises: None
Create Date: 2026-08-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "000000000001"

down_revision: Union[str, Sequence[str], None] = None

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial QuantCore schema."""

    # ---------------------------------------------------------
    # 1. Companies
    # ---------------------------------------------------------

    op.create_table(
        "companies",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "sector",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "industry",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "country",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "website",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "market_cap",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_companies_symbol",
        "companies",
        ["symbol"],
        unique=True,
    )

    # ---------------------------------------------------------
    # 2. Prices
    # ---------------------------------------------------------

    op.create_table(
        "prices",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "date",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "open",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "high",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "low",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "close",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "volume",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "dividends",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "stock_splits",
            sa.Float(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_prices_company_id",
        "prices",
        ["company_id"],
        unique=False,
    )

    op.create_index(
        "ix_prices_company_date",
        "prices",
        ["company_id", "date"],
        unique=True,
    )

    # ---------------------------------------------------------
    # 3. News
    # ---------------------------------------------------------

    op.create_table(
        "news",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "publisher",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "url",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )

    op.create_index(
        "ix_news_company_id",
        "news",
        ["company_id"],
        unique=False,
    )

    op.create_index(
        "ix_news_company_date",
        "news",
        ["company_id", "published_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the initial QuantCore schema."""

    op.drop_index(
        "ix_news_company_date",
        table_name="news",
    )

    op.drop_index(
        "ix_news_company_id",
        table_name="news",
    )

    op.drop_table("news")

    op.drop_index(
        "ix_prices_company_date",
        table_name="prices",
    )

    op.drop_index(
        "ix_prices_company_id",
        table_name="prices",
    )

    op.drop_table("prices")

    op.drop_index(
        "ix_companies_symbol",
        table_name="companies",
    )

    op.drop_table("companies")