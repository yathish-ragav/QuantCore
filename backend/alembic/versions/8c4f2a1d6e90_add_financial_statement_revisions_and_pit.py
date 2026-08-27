"""add financial statement revisions and point-in-time reads

Revision ID: 8c4f2a1d6e90
Revises: 7d3e9f1a2b4c
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c4f2a1d6e90"
down_revision: Union[str, Sequence[str], None] = "7d3e9f1a2b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATEMENT_TYPE = sa.Enum(
    "INCOME",
    "BALANCE_SHEET",
    "CASH_FLOW",
    name="financial_statement_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

PERIOD_TYPE = sa.Enum(
    "ANNUAL",
    "QUARTERLY",
    "TTM",
    "INSTANT",
    name="financial_period_type",
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
    """Create immutable normalized financial statement revisions."""
    op.create_table(
        "financial_statement_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement_type", STATEMENT_TYPE, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("fiscal_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=10), nullable=True),
        sa.Column("period_type", PERIOD_TYPE, nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("filing_form", sa.String(length=20), nullable=True),
        sa.Column("accession_number", sa.String(length=40), nullable=True),
        sa.Column("total_revenue", sa.Float(), nullable=True),
        sa.Column("gross_profit", sa.Float(), nullable=True),
        sa.Column("operating_income", sa.Float(), nullable=True),
        sa.Column("net_income", sa.Float(), nullable=True),
        sa.Column("eps", sa.Float(), nullable=True),
        sa.Column("shares_outstanding", sa.BigInteger(), nullable=True),
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
        sa.Column("operating_cash_flow", sa.Float(), nullable=True),
        sa.Column("capital_expenditure", sa.Float(), nullable=True),
        sa.Column("free_cash_flow", sa.Float(), nullable=True),
        sa.Column("investing_cash_flow", sa.Float(), nullable=True),
        sa.Column("financing_cash_flow", sa.Float(), nullable=True),
        sa.Column("depreciation_and_amortization", sa.Float(), nullable=True),
        sa.Column("stock_based_compensation", sa.Float(), nullable=True),
        sa.Column("dividends_paid", sa.Float(), nullable=True),
        sa.Column("share_repurchases", sa.Float(), nullable=True),
        sa.Column("net_change_in_cash", sa.Float(), nullable=True),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "statement_type", "statement_id", "revision_number",
            name="uq_financial_statement_revision_identity",
        ),
    )

    op.create_index(
        op.f("ix_financial_statement_revisions_company_id"),
        "financial_statement_revisions", ["company_id"], unique=False,
    )
    op.create_index(
        op.f("ix_financial_statement_revisions_statement_id"),
        "financial_statement_revisions", ["statement_id"], unique=False,
    )
    op.create_index(
        op.f("ix_financial_statement_revisions_known_at"),
        "financial_statement_revisions", ["known_at"], unique=False,
    )
    op.create_index(
        op.f("ix_financial_statement_revisions_fiscal_date"),
        "financial_statement_revisions", ["fiscal_date"], unique=False,
    )

    for table_name, statement_type, fields in (
        ("income_statements", "INCOME", (
            "total_revenue", "gross_profit", "operating_income", "net_income",
            "eps", "shares_outstanding",
        )),
        ("balance_sheets", "BALANCE_SHEET", (
            "cash_and_cash_equivalents", "short_term_investments", "accounts_receivable",
            "inventory", "total_current_assets", "property_plant_equipment_net", "goodwill",
            "intangible_assets", "total_assets", "accounts_payable", "short_term_debt",
            "total_current_liabilities", "long_term_debt", "total_liabilities", "total_equity",
            "retained_earnings", "total_debt", "net_debt", "working_capital",
        )),
        ("cash_flow_statements", "CASH_FLOW", (
            "operating_cash_flow", "capital_expenditure", "free_cash_flow", "investing_cash_flow",
            "financing_cash_flow", "depreciation_and_amortization", "stock_based_compensation",
            "dividends_paid", "share_repurchases", "net_change_in_cash",
        )),
    ):
        columns = [
            "statement_type", "statement_id", "company_id", "revision_number",
            "fiscal_date", "period_start", "fiscal_year", "fiscal_period", "period_type",
            "filing_date", "filing_form", "accession_number",
            *fields, "source", "known_at", "source_reference",
        ]
        select_values = [
            f"'{statement_type}'", "id", "company_id", "1", "fiscal_date", "period_start",
            "fiscal_year", "fiscal_period", "period_type", "filing_date", "filing_form",
            "accession_number", *fields, "source", "COALESCE(fetched_at, CURRENT_TIMESTAMP)",
            "source_reference",
        ]
        op.execute(sa.text(
            f"INSERT INTO financial_statement_revisions ({', '.join(columns)}) "
            f"SELECT {', '.join(select_values)} FROM {table_name}"
        ))


def downgrade() -> None:
    op.drop_index(op.f("ix_financial_statement_revisions_fiscal_date"), table_name="financial_statement_revisions")
    op.drop_index(op.f("ix_financial_statement_revisions_known_at"), table_name="financial_statement_revisions")
    op.drop_index(op.f("ix_financial_statement_revisions_statement_id"), table_name="financial_statement_revisions")
    op.drop_index(op.f("ix_financial_statement_revisions_company_id"), table_name="financial_statement_revisions")
    op.drop_table("financial_statement_revisions")
