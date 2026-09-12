"""add persisted research experiment comparison results

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_experiment_comparison_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comparison_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("selection_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("experiment_key", sa.String(length=200), nullable=False),
        sa.Column("definition_version", sa.String(length=50), nullable=False),
        sa.Column("comparison_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "result_fingerprint",
            name="uq_research_experiment_comparison_results_result_fingerprint",
        ),
    )
    op.create_index(
        op.f("ix_research_experiment_comparison_results_comparison_fingerprint"),
        "research_experiment_comparison_results",
        ["comparison_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_research_exp_cmp_results_cmp_recorded_id",
        "research_experiment_comparison_results",
        ["comparison_fingerprint", "recorded_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_research_experiment_comparison_results_selection_fingerprint",
        "research_experiment_comparison_results",
        ["selection_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_experiment_comparison_results_selection_fingerprint",
        table_name="research_experiment_comparison_results",
    )
    op.drop_index(
        "ix_research_exp_cmp_results_cmp_recorded_id",
        table_name="research_experiment_comparison_results",
    )
    op.drop_index(
        op.f("ix_research_experiment_comparison_results_comparison_fingerprint"),
        table_name="research_experiment_comparison_results",
    )
    op.drop_table("research_experiment_comparison_results")
