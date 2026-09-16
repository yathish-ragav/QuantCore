"""Normalize persisted data-source storage for the provider provenance enum.

Revision ID: f6c7d8e9f0a1
Revises: f5b6c7d8e9f0
Create Date: 2026-09-16 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.compiler import IdentifierPreparer


revision: str = "f6c7d8e9f0a1"
down_revision: str | None = "f5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SOURCE_CHECK = "source IN ('SEC', 'FMP', 'YAHOO', 'FRED', 'MASSIVE')"
_SOURCE_CHECK_LEGACY = "source IN ('SEC', 'FMP', 'YAHOO', 'FRED')"


def _source_constraints(bind) -> list[tuple[str, str, int | None]]:
    rows = bind.execute(
        sa.text(
            """
            SELECT
                ns.nspname AS schema_name,
                cls.relname AS table_name,
                con.conname AS constraint_name,
                cols.character_maximum_length AS character_maximum_length
            FROM pg_constraint AS con
            JOIN pg_class AS cls
              ON cls.oid = con.conrelid
            JOIN pg_namespace AS ns
              ON ns.oid = cls.relnamespace
            JOIN pg_attribute AS att
              ON att.attrelid = con.conrelid
             AND att.attnum = ANY(con.conkey)
            JOIN information_schema.columns AS cols
              ON cols.table_schema = ns.nspname
             AND cols.table_name = cls.relname
             AND cols.column_name = att.attname
            WHERE con.contype = 'c'
              AND con.conname = 'data_source'
              AND att.attname = 'source'
              AND ns.nspname = 'public'
            ORDER BY cls.relname
            """
        )
    ).mappings()
    return [
        (
            str(row["table_name"]),
            str(row["constraint_name"]),
            int(row["character_maximum_length"])
            if row["character_maximum_length"] is not None
            else None,
        )
        for row in rows
    ]


def _alter_source_width(bind, table_name: str, current_length: int | None) -> None:
    if current_length is not None and current_length >= 10:
        return

    preparer = IdentifierPreparer(bind.dialect)
    table = preparer.quote(table_name)
    op.execute(
        sa.text(
            f"ALTER TABLE {table} ALTER COLUMN source TYPE VARCHAR(10)"
        )
    )


def upgrade() -> None:
    """Make all shared DataSource columns capable of storing MASSIVE."""
    bind = op.get_bind()
    constraints = _source_constraints(bind)

    for table_name, constraint_name, current_length in constraints:
        _alter_source_width(bind, table_name, current_length)
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.create_check_constraint(
            constraint_name,
            table_name,
            _SOURCE_CHECK,
        )


def downgrade() -> None:
    """Restore the pre-MASSIVE shared DataSource constraint and width."""
    bind = op.get_bind()
    constraints = _source_constraints(bind)

    for table_name, constraint_name, current_length in constraints:
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.create_check_constraint(
            constraint_name,
            table_name,
            _SOURCE_CHECK_LEGACY,
        )
        if current_length is None or current_length > 5:
            preparer = IdentifierPreparer(bind.dialect)
            table = preparer.quote(table_name)
            op.execute(
                sa.text(
                    f"ALTER TABLE {table} ALTER COLUMN source TYPE VARCHAR(5)"
                )
            )
