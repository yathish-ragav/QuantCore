"""add bitemporal security classification history

Revision ID: h1i2j3k4l5m6
Revises: g7h8i9j0k1l2
Create Date: 2026-09-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    security_type = sa.Enum(
        "UNKNOWN",
        "COMMON_STOCK",
        "PREFERRED_STOCK",
        "ADR",
        "ETF",
        "WARRANT",
        "UNIT",
        "RIGHT",
        "SPAC",
        "OTHER",
        name="security_type_history",
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )
    data_source = sa.Enum(
        "SEC",
        "FMP",
        "YAHOO",
        "FRED",
        "MASSIVE",
        "UNKNOWN",
        name="security_classification_source",
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )
    op.create_table(
        "security_classification_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("security_type", security_type, nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", data_source, nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "effective_from",
            "known_at",
            name="uq_security_classification_history_revision",
        ),
    )
    op.create_index(
        "ix_security_classification_history_security_id",
        "security_classification_history",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        "ix_security_classification_history_security_type",
        "security_classification_history",
        ["security_type"],
        unique=False,
    )
    op.create_index(
        "ix_security_classification_history_known_at",
        "security_classification_history",
        ["known_at"],
        unique=False,
    )
    op.create_index(
        "ix_security_classification_history_is_current",
        "security_classification_history",
        ["is_current"],
        unique=False,
    )
    op.create_index(
        "ix_security_classification_history_effective",
        "security_classification_history",
        ["security_id", "effective_from", "effective_to"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_security_classification_history_effective",
        table_name="security_classification_history",
    )
    op.drop_index(
        "ix_security_classification_history_is_current",
        table_name="security_classification_history",
    )
    op.drop_index(
        "ix_security_classification_history_known_at",
        table_name="security_classification_history",
    )
    op.drop_index(
        "ix_security_classification_history_security_type",
        table_name="security_classification_history",
    )
    op.drop_index(
        "ix_security_classification_history_security_id",
        table_name="security_classification_history",
    )
    op.drop_table("security_classification_history")
