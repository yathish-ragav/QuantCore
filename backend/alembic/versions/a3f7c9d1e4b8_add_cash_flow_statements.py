"""add cash flow statements

Revision ID: a3f7c9d1e4b8
Revises: 8f3c1d2a7b6e
Create Date: 2026-08-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f7c9d1e4b8"

down_revision: Union[str, Sequence[str], None] = "8f3c1d2a7b6e"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "cash_flow_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_date", sa.Date(), nullable=False),
        sa.Column("operating_cash_flow", sa.Float(), nullable=True),
        sa.Column("capital_expenditure", sa.Float(), nullable=True),
        sa.Column("free_cash_flow", sa.Float(), nullable=True),
        sa.Column("investing_cash_flow", sa.Float(), nullable=True),
        sa.Column("financing_cash_flow", sa.Float(), nullable=True),
        sa.Column(
            "depreciation_and_amortization",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "stock_based_compensation", sa.Float(), nullable=True
        ),
        sa.Column("dividends_paid", sa.Float(), nullable=True),
        sa.Column("share_repurchases", sa.Float(), nullable=True),
        sa.Column("net_change_in_cash", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_date",
            name="uq_cash_flow_statement_company_fiscal_date",
        ),
    )
    op.create_index(
        op.f("ix_cash_flow_statements_company_id"),
        "cash_flow_statements",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_cash_flow_statements_company_id"),
        table_name="cash_flow_statements",
    )
    op.drop_table("cash_flow_statements")
