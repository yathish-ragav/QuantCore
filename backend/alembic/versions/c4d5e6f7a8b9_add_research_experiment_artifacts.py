"""add research experiment artifact identity and provenance

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_experiment_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=100), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_experiment_runs.run_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
        sa.UniqueConstraint(
            "run_id",
            "artifact_fingerprint",
            name="uq_research_experiment_artifacts_run_fingerprint",
        ),
    )
    op.create_index(
        "ix_research_experiment_artifacts_artifact_fingerprint",
        "research_experiment_artifacts",
        ["artifact_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_research_experiment_artifacts_content_hash",
        "research_experiment_artifacts",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_research_experiment_artifacts_run_created_id",
        "research_experiment_artifacts",
        ["run_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_experiment_artifacts_run_created_id",
        table_name="research_experiment_artifacts",
    )
    op.drop_index(
        "ix_research_experiment_artifacts_content_hash",
        table_name="research_experiment_artifacts",
    )
    op.drop_index(
        "ix_research_experiment_artifacts_artifact_fingerprint",
        table_name="research_experiment_artifacts",
    )
    op.drop_table("research_experiment_artifacts")
