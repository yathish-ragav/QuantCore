"""add SEC filing metadata and filing events

Revision ID: 7b2d1f4c8a90
Revises: 91c4d7e2f5a8
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b2d1f4c8a90"
down_revision: Union[str, Sequence[str], None] = "91c4d7e2f5a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DATA_SOURCE = sa.Enum(
    "SEC",
    "FMP",
    "YAHOO",
    name="data_source",
    native_enum=False,
    create_constraint=True,
)

FILING_EVENT_TYPE = sa.Enum(
    "FILED",
    "AMENDED",
    name="filing_event_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


def upgrade() -> None:
    op.create_table(
        "sec_filings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("accession_number", sa.String(length=40), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("acceptance_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form", sa.String(length=20), nullable=False),
        sa.Column("act", sa.String(length=20), nullable=True),
        sa.Column("file_number", sa.String(length=50), nullable=True),
        sa.Column("film_number", sa.String(length=50), nullable=True),
        sa.Column("items", sa.String(length=1000), nullable=True),
        sa.Column("primary_document", sa.String(length=500), nullable=True),
        sa.Column("primary_doc_description", sa.String(length=1000), nullable=True),
        sa.Column("is_xbrl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_inline_xbrl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=10), nullable=True),
        sa.Column("is_amendment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("filing_url", sa.String(length=1000), nullable=True),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number"),
    )
    op.create_index(
        "ix_sec_filings_company_id",
        "sec_filings",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_accession_number",
        "sec_filings",
        ["accession_number"],
        unique=True,
    )
    op.create_index(
        "ix_sec_filings_filing_date",
        "sec_filings",
        ["filing_date"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_report_date",
        "sec_filings",
        ["report_date"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_acceptance_datetime",
        "sec_filings",
        ["acceptance_datetime"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_form",
        "sec_filings",
        ["form"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_fiscal_year",
        "sec_filings",
        ["fiscal_year"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_is_amendment",
        "sec_filings",
        ["is_amendment"],
        unique=False,
    )
    op.create_index(
        "ix_sec_filings_source",
        "sec_filings",
        ["source"],
        unique=False,
    )

    op.create_table(
        "filing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Integer(), nullable=False),
        sa.Column("event_type", FILING_EVENT_TYPE, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", DATA_SOURCE, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["filing_id"],
            ["sec_filings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "filing_id",
            "event_type",
            "occurred_at",
            name="uq_filing_event_identity",
        ),
    )
    op.create_index(
        "ix_filing_events_filing_id",
        "filing_events",
        ["filing_id"],
        unique=False,
    )
    op.create_index(
        "ix_filing_events_event_type",
        "filing_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_filing_events_occurred_at",
        "filing_events",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_filing_events_occurred_at", table_name="filing_events")
    op.drop_index("ix_filing_events_event_type", table_name="filing_events")
    op.drop_index("ix_filing_events_filing_id", table_name="filing_events")
    op.drop_table("filing_events")

    for index_name in (
        "ix_sec_filings_source",
        "ix_sec_filings_is_amendment",
        "ix_sec_filings_fiscal_year",
        "ix_sec_filings_form",
        "ix_sec_filings_acceptance_datetime",
        "ix_sec_filings_report_date",
        "ix_sec_filings_filing_date",
        "ix_sec_filings_accession_number",
        "ix_sec_filings_company_id",
    ):
        op.drop_index(index_name, table_name="sec_filings")
    op.drop_table("sec_filings")
