"""allow multiple provider-distinct corporate actions on one date

Revision ID: g7h8i9j0k1l2
Revises: fb1c2d3e4f50
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "fb1c2d3e4f50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_corporate_action_identity",
        "corporate_actions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_corporate_action_provider_identity",
        "corporate_actions",
        [
            "security_id",
            "effective_date",
            "action_type",
            "source",
            "source_reference",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_corporate_action_provider_identity",
        "corporate_actions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_corporate_action_identity",
        "corporate_actions",
        [
            "security_id",
            "effective_date",
            "action_type",
        ],
    )
