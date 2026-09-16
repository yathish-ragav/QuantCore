"""add security instrument classification

Revision ID: f9a0b1c2d3e4
Revises: f8b9c0d1e2f3
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "f8b9c0d1e2f3"
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
        name="security_type",
        native_enum=False,
        create_constraint=True,
    )
    op.add_column(
        "securities",
        sa.Column(
            "security_type",
            security_type,
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.create_index(
        "ix_securities_security_type_status",
        "securities",
        ["security_type", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_securities_security_type_status", table_name="securities")
    op.drop_column("securities", "security_type")
