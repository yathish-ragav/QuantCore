"""add corporate action revisions and point-in-time reads

Revision ID: b1c2d3e4f5a6
Revises: 8c4f2a1d6e90
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "8c4f2a1d6e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CORPORATE_ACTION_TYPE = sa.Enum(
    "DIVIDEND", "STOCK_SPLIT", name="corporate_action_type",
    native_enum=False, create_constraint=True, validate_strings=True,
)
DATA_SOURCE = sa.Enum(
    "SEC", "FMP", "YAHOO", "FRED", name="data_source",
    native_enum=False, create_constraint=True, validate_strings=True,
)


def upgrade() -> None:
    op.create_table(
        "corporate_action_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("action_type", CORPORATE_ACTION_TYPE, nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("split_ratio", sa.Float(), nullable=True),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["action_id"], ["corporate_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_id", "revision_number", name="uq_corporate_action_revision_identity"),
    )
    op.create_index(op.f("ix_corporate_action_revisions_action_id"), "corporate_action_revisions", ["action_id"], unique=False)
    op.create_index(op.f("ix_corporate_action_revisions_security_id"), "corporate_action_revisions", ["security_id"], unique=False)
    op.create_index(op.f("ix_corporate_action_revisions_effective_date"), "corporate_action_revisions", ["effective_date"], unique=False)
    op.create_index(op.f("ix_corporate_action_revisions_action_type"), "corporate_action_revisions", ["action_type"], unique=False)
    op.create_index(op.f("ix_corporate_action_revisions_known_at"), "corporate_action_revisions", ["known_at"], unique=False)

    op.execute(sa.text(
        "INSERT INTO corporate_action_revisions "
        "(action_id, security_id, revision_number, effective_date, action_type, amount, split_ratio, source, known_at, source_reference) "
        "SELECT id, security_id, 1, effective_date, action_type, amount, split_ratio, source, "
        "COALESCE(fetched_at, CURRENT_TIMESTAMP), source_reference FROM corporate_actions"
    ))


def downgrade() -> None:
    op.drop_index(op.f("ix_corporate_action_revisions_known_at"), table_name="corporate_action_revisions")
    op.drop_index(op.f("ix_corporate_action_revisions_action_type"), table_name="corporate_action_revisions")
    op.drop_index(op.f("ix_corporate_action_revisions_effective_date"), table_name="corporate_action_revisions")
    op.drop_index(op.f("ix_corporate_action_revisions_security_id"), table_name="corporate_action_revisions")
    op.drop_index(op.f("ix_corporate_action_revisions_action_id"), table_name="corporate_action_revisions")
    op.drop_table("corporate_action_revisions")
