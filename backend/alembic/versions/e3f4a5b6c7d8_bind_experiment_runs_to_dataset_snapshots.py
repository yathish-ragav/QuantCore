"""bind experiment runs to concrete dataset snapshots

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RUNS_TABLE = "research_experiment_runs"
DATASET_FINGERPRINT = "dataset_fingerprint"
EXECUTION_INPUT_FINGERPRINT = "execution_input_fingerprint"
DATASET_INDEX = "ix_research_experiment_runs_dataset_fingerprint"
EXECUTION_INPUT_INDEX = "ix_research_experiment_runs_execution_input_fingerprint"


def _column_names(bind) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(RUNS_TABLE)}


def _index_names(bind) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(RUNS_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind)
    indexes = _index_names(bind)

    if DATASET_FINGERPRINT not in columns:
        op.add_column(
            RUNS_TABLE,
            sa.Column(DATASET_FINGERPRINT, sa.String(length=64), nullable=True),
        )

    if EXECUTION_INPUT_FINGERPRINT not in columns:
        op.add_column(
            RUNS_TABLE,
            sa.Column(EXECUTION_INPUT_FINGERPRINT, sa.String(length=64), nullable=True),
        )

    if DATASET_INDEX not in indexes:
        op.create_index(
            DATASET_INDEX,
            RUNS_TABLE,
            [DATASET_FINGERPRINT],
            unique=False,
        )

    if EXECUTION_INPUT_INDEX not in indexes:
        op.create_index(
            EXECUTION_INPUT_INDEX,
            RUNS_TABLE,
            [EXECUTION_INPUT_FINGERPRINT],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = _index_names(bind)
    columns = _column_names(bind)

    if EXECUTION_INPUT_INDEX in indexes:
        op.drop_index(EXECUTION_INPUT_INDEX, table_name=RUNS_TABLE)

    if DATASET_INDEX in indexes:
        op.drop_index(DATASET_INDEX, table_name=RUNS_TABLE)

    if EXECUTION_INPUT_FINGERPRINT in columns:
        op.drop_column(RUNS_TABLE, EXECUTION_INPUT_FINGERPRINT)

    if DATASET_FINGERPRINT in columns:
        op.drop_column(RUNS_TABLE, DATASET_FINGERPRINT)
