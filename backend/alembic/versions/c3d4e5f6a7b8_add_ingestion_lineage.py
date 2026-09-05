"""add ingestion execution lineage

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DATASET = sa.Enum(
    "company",
    "price_history",
    "news",
    "income_statement",
    "cash_flow_statement",
    "balance_sheet",
    "sec_filings",
    "corporate_actions",
    "sec_xbrl_facts",
    name="ingestion_dataset",
    native_enum=False,
    create_constraint=True,
)

SCOPE = sa.Enum(
    "company",
    "security",
    name="ingestion_scope",
    native_enum=False,
    create_constraint=True,
)

DATA_SOURCE = sa.Enum(
    "SEC",
    "FMP",
    "YAHOO",
    "FRED",
    name="data_source",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ingestion_lineage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=False),
        sa.Column("dataset", DATASET, nullable=False),
        sa.Column("scope", SCOPE, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("security_id", sa.Integer(), nullable=True),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "records_processed >= 0",
            name="ck_ingestion_lineage_records_nonnegative",
        ),
        sa.CheckConstraint(
            "(scope = 'company' AND company_id IS NOT NULL AND security_id IS NULL)"
            " OR (scope = 'security' AND security_id IS NOT NULL AND company_id IS NULL)",
            name="ck_ingestion_lineage_scope_entity",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"], ["ingestion_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["security_id"], ["securities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingestion_run_id",
            "company_id",
            "security_id",
            name="uq_ingestion_lineage_run_entity",
        ),
    )
    op.create_index(
        op.f("ix_ingestion_lineage_ingestion_run_id"),
        "ingestion_lineage",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_lineage_dataset"),
        "ingestion_lineage",
        ["dataset"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_lineage_scope"),
        "ingestion_lineage",
        ["scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_lineage_company_id"),
        "ingestion_lineage",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_lineage_security_id"),
        "ingestion_lineage",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_lineage_source"),
        "ingestion_lineage",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    for column in (
        "source",
        "security_id",
        "company_id",
        "scope",
        "dataset",
        "ingestion_run_id",
    ):
        op.drop_index(
            op.f(f"ix_ingestion_lineage_{column}"),
            table_name="ingestion_lineage",
        )
    op.drop_table("ingestion_lineage")
