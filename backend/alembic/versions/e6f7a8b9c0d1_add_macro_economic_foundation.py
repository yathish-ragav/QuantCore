"""add macro economic series and vintage observations

Revision ID: e6f7a8b9c0d1
Revises: d5e7f8a9b0c1
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "macro_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("frequency", sa.String(length=100), nullable=False),
        sa.Column("frequency_short", sa.String(length=20), nullable=True),
        sa.Column("units", sa.String(length=255), nullable=False),
        sa.Column("units_short", sa.String(length=100), nullable=True),
        sa.Column("seasonal_adjustment", sa.String(length=100), nullable=True),
        sa.Column("seasonal_adjustment_short", sa.String(length=20), nullable=True),
        sa.Column("observation_start", sa.Date(), nullable=True),
        sa.Column("observation_end", sa.Date(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source = 'FRED'", name="ck_macro_series_source"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "series_id", name="uq_macro_series_source_series_id"),
    )
    op.create_index("ix_macro_series_series_id", "macro_series", ["series_id"], unique=False)
    op.create_index("ix_macro_series_source", "macro_series", ["source"], unique=False)


    op.create_table(
        "macro_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(60, 18), nullable=True),
        sa.Column("realtime_start", sa.Date(), nullable=False),
        sa.Column("realtime_end", sa.Date(), nullable=False),
        sa.Column("vintage_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.CheckConstraint("source = 'FRED'", name="ck_macro_observation_source"),
        sa.ForeignKeyConstraint(["series_id"], ["macro_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "observation_date",
            "vintage_date",
            name="uq_macro_observation_series_date_vintage",
        ),
    )
    for name, column in (
        ("series_id", "series_id"),
        ("observation_date", "observation_date"),
        ("realtime_start", "realtime_start"),
        ("realtime_end", "realtime_end"),
        ("vintage_date", "vintage_date"),
        ("source", "source"),
    ):
        op.create_index(f"ix_macro_observations_{name}", "macro_observations", [column], unique=False)


def downgrade() -> None:
    for name in (
        "source",
        "vintage_date",
        "realtime_end",
        "realtime_start",
        "observation_date",
        "series_id",
    ):
        op.drop_index(f"ix_macro_observations_{name}", table_name="macro_observations")
    op.drop_table("macro_observations")
    op.drop_index("ix_macro_series_source", table_name="macro_series")
    op.drop_index("ix_macro_series_series_id", table_name="macro_series")
    op.drop_table("macro_series")
