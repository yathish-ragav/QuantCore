"""add SEC XBRL fact observation and revision foundation

Revision ID: d5e7f8a9b0c1
Revises: c4d8e1f2a6b7
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c4d8e1f2a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATASET_VALUES = (
    "'company', 'price_history', 'news', 'income_statement', "
    "'cash_flow_statement', 'balance_sheet', 'sec_filings', "
    "'corporate_actions', 'sec_xbrl_facts'"
)

DATA_SOURCE = sa.Enum(
    "SEC", "FMP", "YAHOO",
    name="data_source", native_enum=False, create_constraint=True, validate_strings=True,
)


def upgrade() -> None:
    op.drop_constraint("ck_ingestion_state_dataset", "ingestion_states", type_="check")
    op.create_check_constraint(
        "ck_ingestion_state_dataset", "ingestion_states",
        "dataset IN (" + DATASET_VALUES + ")",
    )
    op.drop_constraint("ck_ingestion_run_dataset", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_run_dataset", "ingestion_runs",
        "dataset IS NULL OR dataset IN (" + DATASET_VALUES + ")",
    )

    op.create_table(
        "sec_xbrl_fact_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Integer(), nullable=True),
        sa.Column("accession_number", sa.String(length=40), nullable=False),
        sa.Column("taxonomy", sa.String(length=50), nullable=False),
        sa.Column("concept", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Numeric(precision=60, scale=18), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form", sa.String(length=20), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=10), nullable=True),
        sa.Column("frame", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("qtrs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decimals", sa.String(length=40), nullable=True),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["filing_id"], ["sec_filings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_hash"),
        sa.UniqueConstraint(
            "company_id", "accession_number", "taxonomy", "concept", "unit",
            "period_start", "period_end", "frame", "qtrs", "value",
            name="uq_sec_xbrl_fact_observation_identity",
        ),
    )
    for name, column in (
        ("company_id", "company_id"), ("filing_id", "filing_id"),
        ("accession_number", "accession_number"), ("taxonomy", "taxonomy"),
        ("concept", "concept"), ("unit", "unit"), ("period_start", "period_start"),
        ("period_end", "period_end"), ("filed_at", "filed_at"),
        ("accepted_at", "accepted_at"), ("form", "form"),
        ("fiscal_year", "fiscal_year"), ("frame", "frame"),
    ):
        op.create_index(f"ix_sec_xbrl_fact_observations_{name}", "sec_xbrl_fact_observations", [column], unique=False)


def downgrade() -> None:
    for name in (
        "fiscal_year", "form", "accepted_at", "filed_at", "period_end",
        "period_start", "unit", "concept", "taxonomy", "accession_number",
        "filing_id", "company_id",
    ):
        op.drop_index(f"ix_sec_xbrl_fact_observations_{name}", table_name="sec_xbrl_fact_observations")
    op.drop_table("sec_xbrl_fact_observations")

    op.drop_constraint("ck_ingestion_run_dataset", "ingestion_runs", type_="check")
    old_values = (
        "'company', 'price_history', 'news', 'income_statement', "
        "'cash_flow_statement', 'balance_sheet', 'sec_filings', 'corporate_actions'"
    )
    op.create_check_constraint(
        "ck_ingestion_run_dataset", "ingestion_runs",
        "dataset IS NULL OR dataset IN (" + old_values + ")",
    )
    op.drop_constraint("ck_ingestion_state_dataset", "ingestion_states", type_="check")
    op.create_check_constraint(
        "ck_ingestion_state_dataset", "ingestion_states",
        "dataset IN (" + old_values + ")",
    )
