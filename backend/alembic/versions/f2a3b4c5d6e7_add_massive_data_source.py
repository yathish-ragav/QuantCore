"""add MASSIVE as a production market-data source

Revision ID: f2a3b4c5d6e7
Revises: e0f1a2b3c4d5
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SOURCE_VALUES = ("SEC", "FMP", "YAHOO", "FRED", "MASSIVE")
SOURCE_CHECK_SQL = "source IN ('SEC', 'FMP', 'YAHOO', 'FRED', 'MASSIVE')"


def _source_checks(bind) -> list[tuple[str, str]]:
    rows = bind.execute(
        sa.text(
            """
            SELECT
                ns.nspname AS schema_name,
                cls.relname AS table_name,
                con.conname AS constraint_name
            FROM pg_constraint AS con
            JOIN pg_class AS cls
              ON cls.oid = con.conrelid
            JOIN pg_namespace AS ns
              ON ns.oid = cls.relnamespace
            WHERE con.contype = 'c'
              AND pg_get_constraintdef(con.oid) LIKE '%source%'
              AND pg_get_constraintdef(con.oid) LIKE '%''FMP''%'
              AND pg_get_constraintdef(con.oid) LIKE '%''YAHOO''%'
              AND pg_get_constraintdef(con.oid) LIKE '%''FRED''%'
            ORDER BY ns.nspname, cls.relname, con.conname
            """
        )
    ).mappings()
    return [
        (str(row["table_name"]), str(row["constraint_name"]))
        for row in rows
        if str(row["schema_name"]) == "public"
    ]


def upgrade() -> None:
    bind = op.get_bind()

    for table_name, constraint_name in _source_checks(bind):
        op.drop_constraint(
            constraint_name,
            table_name,
            type_="check",
        )
        op.create_check_constraint(
            constraint_name,
            table_name,
            SOURCE_CHECK_SQL,
        )


def downgrade() -> None:
    bind = op.get_bind()

    for table_name, constraint_name in _source_checks(bind):
        op.drop_constraint(
            constraint_name,
            table_name,
            type_="check",
        )
        op.create_check_constraint(
            constraint_name,
            table_name,
            "source IN ('SEC', 'FMP', 'YAHOO', 'FRED')",
        )
