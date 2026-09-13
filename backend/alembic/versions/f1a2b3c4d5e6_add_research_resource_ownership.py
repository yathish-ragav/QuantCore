"""add research resource ownership identity fields

Revision ID: f1a2b3c4d5e6
Revises: e3f4a5b6c7d8
Create Date: 2026-09-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    run_columns = _columns(bind, "research_experiment_runs")
    if "owner_issuer" not in run_columns:
        op.add_column(
            "research_experiment_runs",
            sa.Column("owner_issuer", sa.String(length=500), nullable=True),
        )
    if "owner_subject" not in run_columns:
        op.add_column(
            "research_experiment_runs",
            sa.Column("owner_subject", sa.String(length=255), nullable=True),
        )

    run_indexes = _indexes(bind, "research_experiment_runs")
    if "ix_research_experiment_runs_owner_submitted_id" not in run_indexes:
        op.create_index(
            "ix_research_experiment_runs_owner_submitted_id",
            "research_experiment_runs",
            ["owner_issuer", "owner_subject", "submitted_at", "id"],
            unique=False,
        )

    comparison_columns = _columns(bind, "research_experiment_comparison_results")
    if "owner_issuer" not in comparison_columns:
        op.add_column(
            "research_experiment_comparison_results",
            sa.Column("owner_issuer", sa.String(length=500), nullable=True),
        )
    if "owner_subject" not in comparison_columns:
        op.add_column(
            "research_experiment_comparison_results",
            sa.Column("owner_subject", sa.String(length=255), nullable=True),
        )

    comparison_constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(
            "research_experiment_comparison_results"
        )
    }
    legacy_constraint = (
        "uq_research_experiment_comparison_results_result_fingerprint"
    )
    if legacy_constraint in comparison_constraints:
        op.drop_constraint(
            legacy_constraint,
            "research_experiment_comparison_results",
            type_="unique",
        )

    comparison_constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(
            "research_experiment_comparison_results"
        )
    }
    owner_constraint = (
        "uq_research_experiment_comparison_results_owner_result_fingerprint"
    )
    if owner_constraint not in comparison_constraints:
        op.create_unique_constraint(
            owner_constraint,
            "research_experiment_comparison_results",
            ["owner_issuer", "owner_subject", "result_fingerprint"],
        )

    comparison_indexes = _indexes(bind, "research_experiment_comparison_results")
    if "ix_research_experiment_comparison_results_owner_recorded_id" not in comparison_indexes:
        op.create_index(
            "ix_research_experiment_comparison_results_owner_recorded_id",
            "research_experiment_comparison_results",
            ["owner_issuer", "owner_subject", "recorded_at", "id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    comparison_indexes = _indexes(bind, "research_experiment_comparison_results")
    if "ix_research_experiment_comparison_results_owner_recorded_id" in comparison_indexes:
        op.drop_index(
            "ix_research_experiment_comparison_results_owner_recorded_id",
            table_name="research_experiment_comparison_results",
        )
    comparison_constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(
            "research_experiment_comparison_results"
        )
    }
    owner_constraint = (
        "uq_research_experiment_comparison_results_owner_result_fingerprint"
    )
    if owner_constraint in comparison_constraints:
        op.drop_constraint(
            owner_constraint,
            "research_experiment_comparison_results",
            type_="unique",
        )
    comparison_constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(
            "research_experiment_comparison_results"
        )
    }
    legacy_constraint = (
        "uq_research_experiment_comparison_results_result_fingerprint"
    )
    if legacy_constraint not in comparison_constraints:
        op.create_unique_constraint(
            legacy_constraint,
            "research_experiment_comparison_results",
            ["result_fingerprint"],
        )

    comparison_columns = _columns(bind, "research_experiment_comparison_results")
    if "owner_subject" in comparison_columns:
        op.drop_column("research_experiment_comparison_results", "owner_subject")
    if "owner_issuer" in comparison_columns:
        op.drop_column("research_experiment_comparison_results", "owner_issuer")

    run_indexes = _indexes(bind, "research_experiment_runs")
    if "ix_research_experiment_runs_owner_submitted_id" in run_indexes:
        op.drop_index(
            "ix_research_experiment_runs_owner_submitted_id",
            table_name="research_experiment_runs",
        )
    run_columns = _columns(bind, "research_experiment_runs")
    if "owner_subject" in run_columns:
        op.drop_column("research_experiment_runs", "owner_subject")
    if "owner_issuer" in run_columns:
        op.drop_column("research_experiment_runs", "owner_issuer")
