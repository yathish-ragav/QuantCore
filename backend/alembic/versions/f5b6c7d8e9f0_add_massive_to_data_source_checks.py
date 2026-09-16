"""Allow MASSIVE as a persisted data source.

Revision ID: f5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-09-16 00:15:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "f5b6c7d8e9f0"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DATA_SOURCE_VALUES = ("SEC", "FMP", "YAHOO", "FRED", "MASSIVE")


def _constraint_expression(column: str = "source") -> str:
    values = ", ".join(f"'{value}'" for value in _DATA_SOURCE_VALUES)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Allow MASSIVE as a persisted data source."""
    for table_name in ("prices", "price_observation_revisions"):
        op.drop_constraint(
            "data_source",
            table_name,
            type_="check",
        )
        op.create_check_constraint(
            "data_source",
            table_name,
            _constraint_expression(),
        )


def downgrade() -> None:
    """Remove MASSIVE from the persisted data-source values."""
    legacy_values = ", ".join(
        f"'{value}'" for value in _DATA_SOURCE_VALUES if value != "MASSIVE"
    )

    for table_name in ("prices", "price_observation_revisions"):
        op.drop_constraint(
            "data_source",
            table_name,
            type_="check",
        )
        op.create_check_constraint(
            "data_source",
            table_name,
            f"source IN ({legacy_values})",
        )
