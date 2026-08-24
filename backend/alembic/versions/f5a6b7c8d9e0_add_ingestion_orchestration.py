"""add ingestion orchestration and freshness state

Revision ID: f5a6b7c8d9e0
Revises: e1f4a8b9c2d3
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e1f4a8b9c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DATASET_VALUES = (
    "'company', 'price_history', 'news', "
    "'income_statement', 'cash_flow_statement', 'balance_sheet'"
)


def upgrade() -> None:
    op.create_table(
        "ingestion_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("security_id", sa.Integer(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_source", sa.String(length=50), nullable=True),
        sa.Column("last_success_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset",
            "company_id",
            name="uq_ingestion_state_dataset_company",
        ),
        sa.UniqueConstraint(
            "dataset",
            "security_id",
            name="uq_ingestion_state_dataset_security",
        ),
        sa.CheckConstraint(
            f"dataset IN ({DATASET_VALUES})",
            name="ck_ingestion_state_dataset",
        ),
        sa.CheckConstraint(
            """
            (scope = 'company' AND company_id IS NOT NULL AND security_id IS NULL)
            OR
            (scope = 'security' AND security_id IS NOT NULL AND company_id IS NULL)
            """,
            name="ck_ingestion_state_scope_entity",
        ),
    )

    op.create_index(
        op.f("ix_ingestion_states_dataset"),
        "ingestion_states",
        ["dataset"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_states_scope"),
        "ingestion_states",
        ["scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_states_company_id"),
        "ingestion_states",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_states_security_id"),
        "ingestion_states",
        ["security_id"],
        unique=False,
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="RUNNING"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(length=4000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            f"dataset IS NULL OR dataset IN ({DATASET_VALUES})",
            name="ck_ingestion_run_dataset",
        ),
        sa.CheckConstraint(
            """
            status IN (
                'RUNNING',
                'COMPLETED',
                'COMPLETED_WITH_ERRORS',
                'FAILED'
            )
            """,
            name="ck_ingestion_run_status",
        ),
    )

    op.create_index(
        op.f("ix_ingestion_runs_dataset"),
        "ingestion_runs",
        ["dataset"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_runs_status"),
        "ingestion_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ingestion_runs_status"),
        table_name="ingestion_runs",
    )
    op.drop_index(
        op.f("ix_ingestion_runs_dataset"),
        table_name="ingestion_runs",
    )
    op.drop_table("ingestion_runs")

    op.drop_index(
        op.f("ix_ingestion_states_security_id"),
        table_name="ingestion_states",
    )
    op.drop_index(
        op.f("ix_ingestion_states_company_id"),
        table_name="ingestion_states",
    )
    op.drop_index(
        op.f("ix_ingestion_states_scope"),
        table_name="ingestion_states",
    )
    op.drop_index(
        op.f("ix_ingestion_states_dataset"),
        table_name="ingestion_states",
    )
    op.drop_table("ingestion_states")
