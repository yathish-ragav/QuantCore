"""add immutable PIT-bound research observations

Revision ID: c2d4e5f6a7b8
Revises: b1c2d3e4f5a6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_key", sa.String(length=200), nullable=False),
        sa.Column("definition_version", sa.String(length=50), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(length=2000), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "as_of",
            "observation_key",
            "definition_version",
            name="uq_research_observation_identity",
        ),
    )
    op.create_index(
        op.f("ix_research_observations_security_id"),
        "research_observations",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_observations_as_of"),
        "research_observations",
        ["as_of"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_observations_observation_key"),
        "research_observations",
        ["observation_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_observations_input_fingerprint"),
        "research_observations",
        ["input_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_research_observations_input_fingerprint"),
        table_name="research_observations",
    )
    op.drop_index(
        op.f("ix_research_observations_observation_key"),
        table_name="research_observations",
    )
    op.drop_index(
        op.f("ix_research_observations_as_of"),
        table_name="research_observations",
    )
    op.drop_index(
        op.f("ix_research_observations_security_id"),
        table_name="research_observations",
    )
    op.drop_table("research_observations")
