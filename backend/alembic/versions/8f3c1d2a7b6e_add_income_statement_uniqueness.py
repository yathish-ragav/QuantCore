"""add income statement uniqueness

Revision ID: 8f3c1d2a7b6e
Revises: c1a7d9e4b2f1
Create Date: 2026-08-17

"""

from typing import Sequence, Union

from alembic import op


revision: str = "8f3c1d2a7b6e"

down_revision: Union[str, Sequence[str], None] = "c1a7d9e4b2f1"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enforce one income statement per company and fiscal date."""

    op.create_unique_constraint(
        "uq_income_statement_company_fiscal_date",
        "income_statements",
        ["company_id", "fiscal_date"],
    )


def downgrade() -> None:
    """Remove income statement company/fiscal-date uniqueness."""

    op.drop_constraint(
        "uq_income_statement_company_fiscal_date",
        "income_statements",
        type_="unique",
    )