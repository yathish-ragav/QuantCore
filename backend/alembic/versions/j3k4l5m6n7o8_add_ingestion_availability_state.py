"""Persist non-retryable dataset availability outcomes.

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "j3k4l5m6n7o8"
down_revision: str | None = "i2j3k4l5m6n7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OUTCOME_CHECK = "ck_ingestion_state_last_outcome"
INDEX_NAME = "ix_ingestion_states_outcome_next_check"


def upgrade() -> None:
    op.add_column(
        "ingestion_states",
        sa.Column("last_outcome", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "ingestion_states",
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        OUTCOME_CHECK,
        "ingestion_states",
        "last_outcome IS NULL OR last_outcome IN ('SUCCESS', 'FAILURE', 'UNAVAILABLE')",
    )
    op.create_index(
        INDEX_NAME,
        "ingestion_states",
        ["last_outcome", "next_check_at"],
    )

    # Reconcile the known polluted CompanyFacts states discovered by the
    # production ingestion audit. A SEC CompanyFacts 404 is a capability/data
    # availability outcome, not a retryable provider failure.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE ingestion_states
            SET last_outcome = 'UNAVAILABLE',
                next_check_at = COALESCE(last_attempt_at, CURRENT_TIMESTAMP) + INTERVAL '30 days',
                consecutive_failures = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE dataset IN (
                'balance_sheet',
                'cash_flow_statement',
                'income_statement',
                'sec_xbrl_facts'
            )
              AND scope = 'company'
              AND last_error = 'SEC CompanyFacts is not available for this CIK.'
            """
        )
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="ingestion_states")
    op.drop_constraint(OUTCOME_CHECK, "ingestion_states", type_="check")
    op.drop_column("ingestion_states", "next_check_at")
    op.drop_column("ingestion_states", "last_outcome")
