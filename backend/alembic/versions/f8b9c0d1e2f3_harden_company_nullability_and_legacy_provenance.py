"""Harden company enrichment nullability and legacy provenance.

Revision ID: f8b9c0d1e2f3
Revises: f6c7d8e9f0a1
Create Date: 2026-09-16 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f8b9c0d1e2f3"
down_revision: str | None = "f6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SOURCE_VALUES = ("SEC", "FMP", "YAHOO", "FRED", "MASSIVE", "UNKNOWN")
_SOURCE_CHECK = "source IN ('SEC', 'FMP', 'YAHOO', 'FRED', 'MASSIVE', 'UNKNOWN')"
_SOURCE_CHECK_LEGACY = "source IN ('SEC', 'FMP', 'YAHOO', 'FRED', 'MASSIVE')"


def _source_constraints(bind) -> list[tuple[str, str]]:
    rows = bind.execute(
        sa.text(
            """
            SELECT
                ns.nspname AS schema_name,
                cls.relname AS table_name,
                con.conname AS constraint_name
            FROM pg_constraint AS con
            JOIN pg_class AS cls ON cls.oid = con.conrelid
            JOIN pg_namespace AS ns ON ns.oid = cls.relnamespace
            JOIN pg_attribute AS att
              ON att.attrelid = con.conrelid
             AND att.attnum = ANY(con.conkey)
            WHERE con.contype = 'c'
              AND con.conname = 'data_source'
              AND att.attname = 'source'
            ORDER BY cls.relname, con.conname
            """
        )
    ).mappings()
    return [
        (str(row["table_name"]), str(row["constraint_name"]))
        for row in rows
        if str(row["schema_name"]) == "public"
    ]


def upgrade() -> None:
    """Represent absent enrichment as NULL and explicitly quarantine unknown provenance."""
    bind = op.get_bind()

    for column_name in ("sector", "industry", "country", "website"):
        op.alter_column(
            "companies",
            column_name,
            existing_type={
                "sector": sa.VARCHAR(length=255),
                "industry": sa.VARCHAR(length=255),
                "country": sa.VARCHAR(length=100),
                "website": sa.VARCHAR(length=500),
            }[column_name],
            nullable=True,
        )


    # Empty strings were the old universe placeholder. They carry no information.
    op.execute(
        sa.text(
            """
            UPDATE companies
               SET sector = NULL
             WHERE sector = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE companies
               SET industry = NULL
             WHERE industry = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE companies
               SET country = NULL
             WHERE country = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE companies
               SET website = NULL
             WHERE website = ''
            """
        )
    )

    for table_name, constraint_name in _source_constraints(bind):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.create_check_constraint(constraint_name, table_name, _SOURCE_CHECK)

    # Preserve legacy values without inventing a provider. A real provider may
    # subsequently replace UNKNOWN and establish authoritative provenance.
    op.execute(
        sa.text(
            """
            INSERT INTO company_field_provenance
                (company_id, field_name, source, fetched_at, source_reference)
            SELECT c.id, v.field_name, 'UNKNOWN', CURRENT_TIMESTAMP,
                   'legacy:provenance-unavailable'
              FROM companies c
              CROSS JOIN LATERAL (
                    VALUES
                        ('sector', c.sector),
                        ('industry', c.industry),
                        ('country', c.country),
                        ('website', c.website)
              ) AS v(field_name, field_value)
             WHERE v.field_value IS NOT NULL
               AND v.field_value <> ''
               AND NOT EXISTS (
                    SELECT 1
                      FROM company_field_provenance p
                     WHERE p.company_id = c.id
                       AND p.field_name = v.field_name
               )
            """
        )
    )


def downgrade() -> None:
    """Restore the previous source set and non-null enrichment columns."""
    bind = op.get_bind()

    for table_name, constraint_name in _source_constraints(bind):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.create_check_constraint(constraint_name, table_name, _SOURCE_CHECK_LEGACY)

    op.execute(
        sa.text(
            """
            DELETE FROM company_field_provenance
             WHERE source = 'UNKNOWN'
               AND source_reference = 'legacy:provenance-unavailable'
            """
        )
    )

    # Empty-string placeholders are the only safe reversible representation.
    for column_name, length in (
        ("sector", 255),
        ("industry", 255),
        ("country", 100),
        ("website", 500),
    ):
        op.execute(
            sa.text(
                f"UPDATE companies SET {column_name} = '' WHERE {column_name} IS NULL"
            )
        )
        op.alter_column(
            "companies",
            column_name,
            existing_type=sa.VARCHAR(length=length),
            nullable=False,
        )
