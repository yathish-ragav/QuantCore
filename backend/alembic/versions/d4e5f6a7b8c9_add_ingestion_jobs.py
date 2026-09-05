"""add persistent ingestion job execution boundary

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset", sa.String(length=50), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=True),
        sa.Column("target_limit", sa.Integer(), nullable=True),
        sa.Column("only_stale", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="QUEUED"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.String(length=4000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_ingestion_job_idempotency"),
        sa.CheckConstraint("target_limit IS NULL OR target_limit > 0", name="ck_ingestion_job_limit_positive"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ingestion_job_attempt_nonnegative"),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED','CANCELLED')",
            name="ck_ingestion_job_status",
        ),
        sa.CheckConstraint(
            "dataset IN ('company','price_history','news','income_statement',"
            "'cash_flow_statement','balance_sheet','sec_filings',"
            "'corporate_actions','sec_xbrl_facts')",
            name="ck_ingestion_job_dataset",
        ),
    )
    op.create_index("ix_ingestion_jobs_dataset", "ingestion_jobs", ["dataset"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_request_fingerprint", "ingestion_jobs", ["request_fingerprint"])

    # ingestion_runs already exists on the production PostgreSQL schema.
    # Add the nullable job reference and attempt number directly so the
    # migration does not rebuild the table (important because ingestion_lineage
    # already references ingestion_runs).
    op.add_column(
        "ingestion_runs",
        sa.Column("job_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ingestion_runs",
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        "fk_ingestion_run_job",
        "ingestion_runs",
        "ingestion_jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ingestion_runs_job_id",
        "ingestion_runs",
        ["job_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_ingestion_run_job_attempt",
        "ingestion_runs",
        ["job_id", "attempt_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_ingestion_run_job_attempt", "ingestion_runs", type_="unique")
    op.drop_index("ix_ingestion_runs_job_id", table_name="ingestion_runs")
    op.drop_constraint("fk_ingestion_run_job", "ingestion_runs", type_="foreignkey")
    op.drop_column("ingestion_runs", "attempt_number")
    op.drop_column("ingestion_runs", "job_id")

    op.drop_index("ix_ingestion_jobs_request_fingerprint", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_dataset", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
