"""add ingestion runtime hot-path indexes

Revision ID: f0a1b2c3d4e5
Revises: d5f6a7b8c9d0
Create Date: 2026-09-07
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "d5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_ingestion_jobs_status_submitted_at_id",
        "ingestion_jobs",
        ["status", "submitted_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_schedules_enabled_next_run_at_id",
        "ingestion_schedules",
        ["enabled", "next_run_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingestion_schedules_enabled_next_run_at_id",
        table_name="ingestion_schedules",
    )
    op.drop_index(
        "ix_ingestion_jobs_status_submitted_at_id",
        table_name="ingestion_jobs",
    )
