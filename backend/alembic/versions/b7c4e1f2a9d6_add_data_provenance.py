"""add data provenance foundation

Revision ID: b7c4e1f2a9d6
Revises: a3f7c9d1e4b8
Create Date: 2026-08-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c4e1f2a9d6"
down_revision: Union[str, Sequence[str], None] = "a3f7c9d1e4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DATA_SOURCE = sa.Enum(
    "SEC",
    "FMP",
    "YAHOO",
    name="data_source",
    native_enum=False,
    create_constraint=True,
)

COMPANY_FIELD = sa.Enum(
    "cik",
    "name",
    "sector",
    "industry",
    "country",
    "website",
    "market_cap",
    name="company_field",
    native_enum=False,
    create_constraint=True,
)


def _add_provenance_columns(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column("source", DATA_SOURCE, nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=True,
        ),
    )
    op.create_index(
        op.f(f"ix_{table_name}_source"),
        table_name,
        ["source"],
        unique=False,
    )


def upgrade() -> None:
    """Upgrade schema."""

    for table_name in (
        "prices",
        "income_statements",
        "cash_flow_statements",
        "news",
        "securities",
    ):
        _add_provenance_columns(table_name)

    op.create_table(
        "company_field_provenance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "field_name",
            COMPANY_FIELD,
            nullable=False,
        ),
        sa.Column(
            "source",
            DATA_SOURCE,
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "field_name",
            name="uq_company_field_provenance_company_field",
        ),
    )

    op.create_index(
        op.f("ix_company_field_provenance_company_id"),
        "company_field_provenance",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_field_provenance_field_name"),
        "company_field_provenance",
        ["field_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_field_provenance_source"),
        "company_field_provenance",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_company_field_provenance_source"),
        table_name="company_field_provenance",
    )
    op.drop_index(
        op.f("ix_company_field_provenance_field_name"),
        table_name="company_field_provenance",
    )
    op.drop_index(
        op.f("ix_company_field_provenance_company_id"),
        table_name="company_field_provenance",
    )
    op.drop_table("company_field_provenance")

    for table_name in (
        "securities",
        "news",
        "cash_flow_statements",
        "income_statements",
        "prices",
    ):
        op.drop_index(
            op.f(f"ix_{table_name}_source"),
            table_name=table_name,
        )
        op.drop_column(table_name, "source_reference")
        op.drop_column(table_name, "fetched_at")
        op.drop_column(table_name, "source")
