"""add financial statement temporal and filing identity

Revision ID: 91c4d7e2f5a8
Revises: f5a6b7c8d9e0
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91c4d7e2f5a8"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


STATEMENT_TABLES = (
    "income_statements",
    "cash_flow_statements",
    "balance_sheets",
)


def upgrade() -> None:
    """Add explicit period and filing identity to all financial statements."""
    for table_name in STATEMENT_TABLES:
        op.add_column(
            table_name,
            sa.Column("period_start", sa.Date(), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("fiscal_year", sa.Integer(), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("fiscal_period", sa.String(length=10), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column(
                "period_type",
                PERIOD_TYPE,
                nullable=True,
            ),
        )
        op.add_column(
            table_name,
            sa.Column("filing_date", sa.Date(), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("filing_form", sa.String(length=20), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("accession_number", sa.String(length=40), nullable=True),
        )

        op.create_index(
            op.f(f"ix_{table_name}_fiscal_year"),
            table_name,
            ["fiscal_year"],
            unique=False,
        )
        op.create_index(
            op.f(f"ix_{table_name}_period_type"),
            table_name,
            ["period_type"],
            unique=False,
        )
        op.create_index(
            op.f(f"ix_{table_name}_filing_date"),
            table_name,
            ["filing_date"],
            unique=False,
        )
        op.create_index(
            op.f(f"ix_{table_name}_accession_number"),
            table_name,
            ["accession_number"],
            unique=False,
        )

    # Existing statement rows predate explicit period semantics. Their
    # fiscal_date is the period end, and the current implementation only
    # stores annual statements. Balance sheets are instantaneous observations.
    for table_name in ("income_statements", "cash_flow_statements"):
        op.execute(
            sa.text(
                f"UPDATE {table_name} "
                "SET fiscal_year = EXTRACT(YEAR FROM fiscal_date)::integer, "
                "fiscal_period = 'FY', period_type = 'ANNUAL' "
                "WHERE period_type IS NULL"
            )
        )

    op.execute(
        sa.text(
            "UPDATE balance_sheets "
            "SET fiscal_year = EXTRACT(YEAR FROM fiscal_date)::integer, "
            "fiscal_period = 'FY', period_type = 'INSTANT' "
            "WHERE period_type IS NULL"
        )
    )

    for table_name in STATEMENT_TABLES:
        op.alter_column(
            table_name,
            "period_type",
            nullable=False,
        )

    op.drop_constraint(
        "uq_income_statement_company_fiscal_date",
        "income_statements",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_income_statement_company_period",
        "income_statements",
        ["company_id", "fiscal_date", "period_type"],
    )

    op.drop_constraint(
        "uq_cash_flow_statement_company_fiscal_date",
        "cash_flow_statements",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_cash_flow_statement_company_period",
        "cash_flow_statements",
        ["company_id", "fiscal_date", "period_type"],
    )

    op.drop_constraint(
        "uq_balance_sheet_company_fiscal_date",
        "balance_sheets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_balance_sheet_company_period",
        "balance_sheets",
        ["company_id", "fiscal_date", "period_type"],
    )


def downgrade() -> None:
    """Restore the previous fiscal-date-only identity."""
    for table_name, new_name, old_name in (
        (
            "income_statements",
            "uq_income_statement_company_period",
            "uq_income_statement_company_fiscal_date",
        ),
        (
            "cash_flow_statements",
            "uq_cash_flow_statement_company_period",
            "uq_cash_flow_statement_company_fiscal_date",
        ),
        (
            "balance_sheets",
            "uq_balance_sheet_company_period",
            "uq_balance_sheet_company_fiscal_date",
        ),
    ):
        op.drop_constraint(new_name, table_name, type_="unique")
        op.create_unique_constraint(
            old_name,
            table_name,
            ["company_id", "fiscal_date"],
        )

        for index_column in (
            "accession_number",
            "filing_date",
            "period_type",
            "fiscal_year",
        ):
            op.drop_index(
                op.f(f"ix_{table_name}_{index_column}"),
                table_name=table_name,
            )

        for column in (
            "accession_number",
            "filing_form",
            "filing_date",
            "period_type",
            "fiscal_period",
            "fiscal_year",
            "period_start",
        ):
            op.drop_column(table_name, column)
