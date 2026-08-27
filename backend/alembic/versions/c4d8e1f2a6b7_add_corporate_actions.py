"""add corporate actions data layer

Revision ID: c4d8e1f2a6b7
Revises: 7b2d1f4c8a90
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d8e1f2a6b7"
down_revision: Union[str, Sequence[str], None] = "7b2d1f4c8a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CORPORATE_ACTION_TYPE = sa.Enum(
    "DIVIDEND",
    "STOCK_SPLIT",
    name="corporate_action_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

DATA_SOURCE = sa.Enum(
    "SEC",
    "FMP",
    "YAHOO",
    name="data_source",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

DATASET_VALUES = (
    "'company', 'price_history', 'news', "
    "'income_statement', 'cash_flow_statement', 'balance_sheet', "
    "'sec_filings', 'corporate_actions'"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_state_dataset",
        "ingestion_states",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_state_dataset",
        "ingestion_states",
        "dataset IN (" + DATASET_VALUES + ")",
    )

    op.drop_constraint(
        "ck_ingestion_run_dataset",
        "ingestion_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_run_dataset",
        "ingestion_runs",
        "dataset IS NULL OR dataset IN (" + DATASET_VALUES + ")",
    )

    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("action_type", CORPORATE_ACTION_TYPE, nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("split_ratio", sa.Float(), nullable=True),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "effective_date",
            "action_type",
            name="uq_corporate_action_identity",
        ),
    )
    op.create_index(
        "ix_corporate_actions_security_id",
        "corporate_actions",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        "ix_corporate_actions_effective_date",
        "corporate_actions",
        ["effective_date"],
        unique=False,
    )
    op.create_index(
        "ix_corporate_actions_action_type",
        "corporate_actions",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        "ix_corporate_actions_source",
        "corporate_actions",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    for index_name in (
        "ix_corporate_actions_source",
        "ix_corporate_actions_action_type",
        "ix_corporate_actions_effective_date",
        "ix_corporate_actions_security_id",
    ):
        op.drop_index(index_name, table_name="corporate_actions")
    op.drop_table("corporate_actions")

    op.drop_constraint(
        "ck_ingestion_state_dataset",
        "ingestion_states",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_state_dataset",
        "ingestion_states",
        (
            "dataset IN ('company', 'price_history', 'news', "
            "'income_statement', 'cash_flow_statement', 'balance_sheet', "
            "'sec_filings')"
        ),
    )

    op.drop_constraint(
        "ck_ingestion_run_dataset",
        "ingestion_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_run_dataset",
        "ingestion_runs",
        (
            "dataset IS NULL OR dataset IN ('company', 'price_history', 'news', "
            "'income_statement', 'cash_flow_statement', 'balance_sheet', "
            "'sec_filings')"
        ),
    )
