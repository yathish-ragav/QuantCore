"""add point-in-time market index domain

Revision ID: c7d8e9f0a1b2
Revises: 9b7c6d5e4f30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "9b7c6d5e4f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_indexes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("methodology_reference", sa.String(length=1000), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_market_indexes_key"),
    )
    op.create_index(
        "ix_market_indexes_provider_key",
        "market_indexes",
        ["provider", "key"],
        unique=False,
    )
    op.create_index(
        "ix_market_indexes_is_active",
        "market_indexes",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "market_index_constituents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("weight", sa.Numeric(20, 10), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["index_id"], ["market_indexes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "index_id",
            "security_id",
            "effective_from",
            name="uq_market_index_constituents_start",
        ),
    )
    op.create_index(
        "ix_market_index_constituents_index_id",
        "market_index_constituents",
        ["index_id"],
        unique=False,
    )
    op.create_index(
        "ix_market_index_constituents_security_id",
        "market_index_constituents",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        "ix_market_index_constituents_index_effective",
        "market_index_constituents",
        ["index_id", "effective_from", "effective_to"],
        unique=False,
    )
    op.create_index(
        "ix_market_index_constituents_security_effective",
        "market_index_constituents",
        ["security_id", "effective_from", "effective_to"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_index_constituents_security_effective",
        table_name="market_index_constituents",
    )
    op.drop_index(
        "ix_market_index_constituents_index_effective",
        table_name="market_index_constituents",
    )
    op.drop_index(
        "ix_market_index_constituents_security_id",
        table_name="market_index_constituents",
    )
    op.drop_index(
        "ix_market_index_constituents_index_id",
        table_name="market_index_constituents",
    )
    op.drop_table("market_index_constituents")
    op.drop_index("ix_market_indexes_is_active", table_name="market_indexes")
    op.drop_index("ix_market_indexes_provider_key", table_name="market_indexes")
    op.drop_table("market_indexes")
