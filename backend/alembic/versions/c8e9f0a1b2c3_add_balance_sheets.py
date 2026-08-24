"""add balance sheets

Revision ID: c8e9f0a1b2c3
Revises: b7c4e1f2a9d6
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "b7c4e1f2a9d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "balance_sheets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_date", sa.Date(), nullable=False),
        sa.Column("cash_and_cash_equivalents", sa.Float(), nullable=True),
        sa.Column("short_term_investments", sa.Float(), nullable=True),
        sa.Column("accounts_receivable", sa.Float(), nullable=True),
        sa.Column("inventory", sa.Float(), nullable=True),
        sa.Column("total_current_assets", sa.Float(), nullable=True),
        sa.Column("property_plant_equipment_net", sa.Float(), nullable=True),
        sa.Column("goodwill", sa.Float(), nullable=True),
        sa.Column("intangible_assets", sa.Float(), nullable=True),
        sa.Column("total_assets", sa.Float(), nullable=True),
        sa.Column("accounts_payable", sa.Float(), nullable=True),
        sa.Column("short_term_debt", sa.Float(), nullable=True),
        sa.Column("total_current_liabilities", sa.Float(), nullable=True),
        sa.Column("long_term_debt", sa.Float(), nullable=True),
        sa.Column("total_liabilities", sa.Float(), nullable=True),
        sa.Column("total_equity", sa.Float(), nullable=True),
        sa.Column("retained_earnings", sa.Float(), nullable=True),
        sa.Column("total_debt", sa.Float(), nullable=True),
        sa.Column("net_debt", sa.Float(), nullable=True),
        sa.Column("working_capital", sa.Float(), nullable=True),
        sa.Column("source", sa.Enum(
            "SEC", "FMP", "YAHOO",
            name="data_source",
            native_enum=False,
            create_constraint=True,
        ), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_date",
            name="uq_balance_sheet_company_fiscal_date",
        ),
    )

    op.create_index(
        op.f("ix_balance_sheets_company_id"),
        "balance_sheets",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_balance_sheets_source"),
        "balance_sheets",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_balance_sheets_source"),
        table_name="balance_sheets",
    )
    op.drop_index(
        op.f("ix_balance_sheets_company_id"),
        table_name="balance_sheets",
    )
    op.drop_table("balance_sheets")
