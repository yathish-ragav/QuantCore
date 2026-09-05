"""add persistent ingestion schedules

Revision ID: d5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("dataset", sa.String(length=50), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=True),
        sa.Column("target_limit", sa.Integer(), nullable=True),
        sa.Column("only_stale", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_ingestion_schedule_name"),
        sa.CheckConstraint(
            "interval_seconds >= 60",
            name="ck_ingestion_schedule_interval_positive",
        ),
        sa.CheckConstraint(
            "target_limit IS NULL OR target_limit > 0",
            name="ck_ingestion_schedule_limit_positive",
        ),
        sa.CheckConstraint(
            "dataset IN ('company','price_history','news','income_statement',"
            "'cash_flow_statement','balance_sheet','sec_filings',"
            "'corporate_actions','sec_xbrl_facts')",
            name="ck_ingestion_schedule_dataset",
        ),
    )
    op.create_index(
        "ix_ingestion_schedules_dataset",
        "ingestion_schedules",
        ["dataset"],
    )
    op.create_index(
        "ix_ingestion_schedules_next_run_at",
        "ingestion_schedules",
        ["next_run_at"],
    )
    op.create_index(
        "ix_ingestion_schedules_enabled",
        "ingestion_schedules",
        ["enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_schedules_enabled", table_name="ingestion_schedules")
    op.drop_index("ix_ingestion_schedules_next_run_at", table_name="ingestion_schedules")
    op.drop_index("ix_ingestion_schedules_dataset", table_name="ingestion_schedules")
    op.drop_table("ingestion_schedules")
