"""add persisted research experiment runs

Revision ID: a2b3c4d5e6f7
Revises: f0a1b2c3d4e5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_status = sa.Enum(
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        name="research_experiment_run_status",
        native_enum=False,
        create_constraint=True,
    )
    op.create_table(
        "research_experiment_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("experiment_key", sa.String(length=200), nullable=False),
        sa.Column("definition_version", sa.String(length=50), nullable=False),
        sa.Column("run_input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("definition_payload", sa.JSON(), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.String(length=4000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index(
        op.f("ix_research_experiment_runs_experiment_key"),
        "research_experiment_runs",
        ["experiment_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_experiment_runs_run_input_fingerprint"),
        "research_experiment_runs",
        ["run_input_fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_experiment_runs_status"),
        "research_experiment_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_research_experiment_runs_experiment_status_submitted_id",
        "research_experiment_runs",
        ["experiment_key", "definition_version", "status", "submitted_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_experiment_runs_experiment_status_submitted_id",
        table_name="research_experiment_runs",
    )
    op.drop_index(
        op.f("ix_research_experiment_runs_status"),
        table_name="research_experiment_runs",
    )
    op.drop_index(
        op.f("ix_research_experiment_runs_run_input_fingerprint"),
        table_name="research_experiment_runs",
    )
    op.drop_index(
        op.f("ix_research_experiment_runs_experiment_key"),
        table_name="research_experiment_runs",
    )
    op.drop_table("research_experiment_runs")
