"""add index source licensing and immutable load audit

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_index_data_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("dataset", sa.String(length=255), nullable=False),
        sa.Column("authority", sa.String(length=30), nullable=False),
        sa.Column("license_status", sa.String(length=30), nullable=False),
        sa.Column("storage_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("redistribution_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terms_reference", sa.String(length=2000), nullable=True),
        sa.Column("license_reference", sa.String(length=2000), nullable=True),
        sa.Column("attribution_text", sa.String(length=2000), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_market_index_data_sources_key"),
    )

    op.add_column(
        "market_indexes",
        sa.Column("data_source_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_market_indexes_data_source_id",
        "market_indexes",
        ["data_source_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_market_indexes_data_source_id",
        "market_indexes",
        "market_index_data_sources",
        ["data_source_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "market_index_constituents",
        sa.Column("data_source_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_market_index_constituents_data_source_id",
        "market_index_constituents",
        ["data_source_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_market_index_constituents_data_source_id",
        "market_index_constituents",
        "market_index_data_sources",
        ["data_source_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint(
        "uq_market_index_constituents_start",
        "market_index_constituents",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_market_index_constituents_start_known_at",
        "market_index_constituents",
        ["index_id", "security_id", "effective_from", "known_at"],
    )

    op.create_table(
        "market_index_data_loads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=4000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["index_id"], ["market_indexes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["market_index_data_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "index_id", "data_source_id", "fingerprint",
            name="uq_market_index_data_load_fingerprint",
        ),
    )
    op.create_index(
        "ix_market_index_data_loads_index_id",
        "market_index_data_loads",
        ["index_id"],
        unique=False,
    )
    op.create_index(
        "ix_market_index_data_loads_data_source_id",
        "market_index_data_loads",
        ["data_source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_index_data_loads_data_source_id", table_name="market_index_data_loads")
    op.drop_index("ix_market_index_data_loads_index_id", table_name="market_index_data_loads")
    op.drop_table("market_index_data_loads")

    op.drop_constraint(
        "uq_market_index_constituents_start_known_at",
        "market_index_constituents",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_market_index_constituents_start",
        "market_index_constituents",
        ["index_id", "security_id", "effective_from"],
    )

    op.drop_constraint(
        "fk_market_index_constituents_data_source_id",
        "market_index_constituents",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_market_index_constituents_data_source_id",
        table_name="market_index_constituents",
    )
    op.drop_column("market_index_constituents", "data_source_id")

    op.drop_constraint(
        "fk_market_indexes_data_source_id",
        "market_indexes",
        type_="foreignkey",
    )
    op.drop_index("ix_market_indexes_data_source_id", table_name="market_indexes")
    op.drop_column("market_indexes", "data_source_id")
    op.drop_table("market_index_data_sources")
