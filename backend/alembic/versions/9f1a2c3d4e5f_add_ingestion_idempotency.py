"""add ingestion run idempotency metadata

Revision ID: 9f1a2c3d4e5f
Revises: f7a8b9c0d1e2
Create Date: 2026-09-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f1a2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "c2d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "idempotency_key",
                sa.String(length=128),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "request_fingerprint",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.create_unique_constraint(
            "uq_ingestion_run_dataset_idempotency",
            ["dataset", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.drop_constraint(
            "uq_ingestion_run_dataset_idempotency",
            type_="unique",
        )
        batch_op.drop_column("request_fingerprint")
        batch_op.drop_column("idempotency_key")
