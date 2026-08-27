"""add macro ingestion scheduling and freshness state

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "macro_ingestion_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("series_id", sa.String(length=100), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_vintage", sa.Date(), nullable=True),
        sa.Column("last_success_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "series_id",
            name="uq_macro_ingestion_state_source_series",
        ),
        sa.CheckConstraint("source = 'FRED'", name="ck_macro_ingestion_state_source"),
    )
    op.create_index(
        "ix_macro_ingestion_states_source",
        "macro_ingestion_states",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_macro_ingestion_states_series_id",
        "macro_ingestion_states",
        ["series_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_macro_ingestion_states_series_id", table_name="macro_ingestion_states")
    op.drop_index("ix_macro_ingestion_states_source", table_name="macro_ingestion_states")
    op.drop_table("macro_ingestion_states")
