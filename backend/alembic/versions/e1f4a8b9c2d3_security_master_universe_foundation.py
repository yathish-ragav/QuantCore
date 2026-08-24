"""strengthen security master and universe state

Revision ID: e1f4a8b9c2d3
Revises: c8e9f0a1b2c3
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f4a8b9c2d3"
down_revision: Union[str, Sequence[str], None] = "c8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "uq_security_symbol",
        "securities",
        type_="unique",
    )

    op.add_column(
        "securities",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "securities",
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "securities",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE securities
            SET
                status = 'ACTIVE',
                first_seen_at = CURRENT_TIMESTAMP,
                last_seen_at = CURRENT_TIMESTAMP
            """
        )
    )

    op.alter_column(
        "securities",
        "status",
        nullable=False,
        server_default="ACTIVE",
    )
    op.alter_column(
        "securities",
        "first_seen_at",
        nullable=False,
    )
    op.alter_column(
        "securities",
        "last_seen_at",
        nullable=False,
    )

    op.create_index(
        op.f("ix_securities_exchange"),
        "securities",
        ["exchange"],
        unique=False,
    )
    op.create_index(
        op.f("ix_securities_status"),
        "securities",
        ["status"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_security_company_symbol_exchange",
        "securities",
        ["company_id", "symbol", "exchange"],
    )

    op.create_table(
        "security_identifier_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("exchange", sa.String(length=50), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "symbol",
            "exchange",
            name="uq_security_identifier_history_identity",
        ),
    )

    op.create_index(
        op.f("ix_security_identifier_history_security_id"),
        "security_identifier_history",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_identifier_history_is_current"),
        "security_identifier_history",
        ["is_current"],
        unique=False,
    )

    # Seed the history table from the current security master snapshot.
    op.execute(
        sa.text(
            """
            INSERT INTO security_identifier_history
                (security_id, symbol, exchange, first_seen_at, last_seen_at, is_current)
            SELECT
                id, symbol, exchange, first_seen_at, last_seen_at, TRUE
            FROM securities
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_security_identifier_history_is_current"),
        table_name="security_identifier_history",
    )
    op.drop_index(
        op.f("ix_security_identifier_history_security_id"),
        table_name="security_identifier_history",
    )
    op.drop_table("security_identifier_history")

    op.drop_constraint(
        "uq_security_company_symbol_exchange",
        "securities",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_securities_status"),
        table_name="securities",
    )
    op.drop_index(
        op.f("ix_securities_exchange"),
        table_name="securities",
    )
    op.drop_column("securities", "last_seen_at")
    op.drop_column("securities", "first_seen_at")
    op.drop_column("securities", "status")

    op.create_unique_constraint(
        "uq_security_symbol",
        "securities",
        ["symbol"],
    )
