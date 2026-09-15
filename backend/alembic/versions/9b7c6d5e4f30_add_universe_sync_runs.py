"""add persistent security universe sync runs

Revision ID: 9b7c6d5e4f30
Revises: f1a2b3c4d5e6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b7c6d5e4f30"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "universe_sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_companies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_securities", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inactive_securities", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_universe_sync_runs_status"),
        "universe_sync_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_universe_sync_runs_status"), table_name="universe_sync_runs")
    op.drop_table("universe_sync_runs")
