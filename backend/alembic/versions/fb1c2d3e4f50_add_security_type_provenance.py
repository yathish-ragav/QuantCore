"""add security type provenance

Revision ID: fb1c2d3e4f50
Revises: fa1b2c3d4e5f
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fb1c2d3e4f50"
down_revision: Union[str, Sequence[str], None] = "fa1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "securities",
        sa.Column(
            "security_type_source",
            sa.Enum(
                "SEC",
                "FMP",
                "YAHOO",
                "FRED",
                "MASSIVE",
                "UNKNOWN",
                name="security_type_source",
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "securities",
        sa.Column(
            "security_type_fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "securities",
        sa.Column(
            "security_type_source_reference",
            sa.String(length=1000),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_securities_security_type_source",
        "securities",
        ["security_type_source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_securities_security_type_source",
        table_name="securities",
    )
    op.drop_column("securities", "security_type_source_reference")
    op.drop_column("securities", "security_type_fetched_at")
    op.drop_column("securities", "security_type_source")
