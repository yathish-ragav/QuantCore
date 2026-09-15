"""add security identity mappings and corporate action lifecycle fields

Revision ID: e0f1a2b3c4d5
Revises: d8e9f0a1b2c3
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CORPORATE_ACTION_TYPES = (
    "DIVIDEND",
    "STOCK_SPLIT",
    "MERGER",
    "ACQUISITION",
    "SPIN_OFF",
    "TICKER_CHANGE",
    "EXCHANGE_CHANGE",
    "NAME_CHANGE",
    "DELISTING",
    "SHARE_CLASS_CHANGE",
    "RIGHTS_OFFERING",
    "RETURN_OF_CAPITAL",
    "RECAPITALIZATION",
    "CONVERSION",
    "TENDER_OFFER",
    "LIQUIDATION",
)


def _check_constraints(bind, table: str) -> dict[str, str]:
    return {
        item["name"]: item["sqltext"]
        for item in sa.inspect(bind).get_check_constraints(table)
        if item.get("name")
    }


def _replace_corporate_action_check(bind, table: str) -> None:
    checks = _check_constraints(bind, table)
    for name in ("corporate_action_type", "ck_corporate_action_type"):
        if name in checks:
            op.drop_constraint(name, table, type_="check")

    values = ", ".join(f"'{value}'" for value in CORPORATE_ACTION_TYPES)
    op.create_check_constraint(
        "corporate_action_type",
        table,
        f"action_type IN ({values})",
    )


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Make ticker/exchange history genuinely effective-dated and PIT.
    # ------------------------------------------------------------------
    op.add_column(
        "security_identifier_history",
        sa.Column("effective_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "security_identifier_history",
        sa.Column("effective_to", sa.Date(), nullable=True),
    )
    op.add_column(
        "security_identifier_history",
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "security_identifier_history",
        sa.Column("source", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "security_identifier_history",
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE security_identifier_history
            SET
                effective_from = CAST(first_seen_at AS DATE),
                known_at = last_seen_at,
                source = 'SEC'
            WHERE effective_from IS NULL
            """
        )
    )

    op.alter_column(
        "security_identifier_history",
        "effective_from",
        existing_type=sa.Date(),
        nullable=False,
    )
    op.alter_column(
        "security_identifier_history",
        "known_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.drop_constraint(
        "uq_security_identifier_history_identity",
        "security_identifier_history",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_security_listing_history_revision",
        "security_identifier_history",
        ["security_id", "symbol", "exchange", "effective_from", "known_at"],
    )
    op.create_index(
        "ix_security_listing_history_effective",
        "security_identifier_history",
        ["security_id", "effective_from", "effective_to"],
        unique=False,
    )
    op.create_index(
        "ix_security_identifier_history_known_at",
        "security_identifier_history",
        ["known_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 2. Add durable external security identifiers (CUSIP/ISIN/etc.).
    # ------------------------------------------------------------------
    op.create_table(
        "security_identifiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("identifier_type", sa.String(length=30), nullable=False),
        sa.Column("namespace", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_security_identifier_valid_interval",
        ),
        sa.CheckConstraint(
            "identifier_type IN ('CUSIP', 'ISIN', 'SEDOL', 'FIGI', 'LEI', 'VENDOR')",
            name="ck_security_identifier_type",
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id",
            "identifier_type",
            "namespace",
            "value",
            "valid_from",
            "known_at",
            name="uq_security_identifier_revision",
        ),
    )
    op.create_index(
        "ix_security_identifiers_security_id",
        "security_identifiers",
        ["security_id"],
        unique=False,
    )
    op.create_index(
        "ix_security_identifiers_identifier_type",
        "security_identifiers",
        ["identifier_type"],
        unique=False,
    )
    op.create_index(
        "ix_security_identifier_lookup",
        "security_identifiers",
        ["identifier_type", "namespace", "value", "valid_from"],
        unique=False,
    )
    op.create_index(
        "ix_security_identifier_security_valid",
        "security_identifiers",
        ["security_id", "identifier_type", "namespace", "valid_from", "valid_to"],
        unique=False,
    )
    op.create_index(
        "ix_security_identifier_known_at",
        "security_identifiers",
        ["known_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 3. Preserve identity-impacting corporate-action details.
    # ------------------------------------------------------------------
    for table in ("corporate_actions", "corporate_action_revisions"):
        op.add_column(
            table,
            sa.Column("related_security_id", sa.Integer(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("old_symbol", sa.String(length=20), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("new_symbol", sa.String(length=20), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("old_exchange", sa.String(length=50), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("new_exchange", sa.String(length=50), nullable=True),
        )
        op.create_foreign_key(
            f"{table}_related_security_fkey",
            table,
            "securities",
            ["related_security_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_{table}_related_security_id",
            table,
            ["related_security_id"],
            unique=False,
        )
        _replace_corporate_action_check(bind, table)


def downgrade() -> None:
    bind = op.get_bind()

    for table in ("corporate_action_revisions", "corporate_actions"):
        checks = _check_constraints(bind, table)
        if "corporate_action_type" in checks:
            op.drop_constraint("corporate_action_type", table, type_="check")
        op.create_check_constraint(
            "corporate_action_type",
            table,
            "action_type IN ('DIVIDEND', 'STOCK_SPLIT')",
        )
        op.drop_index(
            f"ix_{table}_related_security_id",
            table_name=table,
        )
        op.drop_constraint(
            f"{table}_related_security_fkey",
            table,
            type_="foreignkey",
        )
        for column in (
            "new_exchange",
            "old_exchange",
            "new_symbol",
            "old_symbol",
            "related_security_id",
        ):
            op.drop_column(table, column)

    op.drop_index(
        "ix_security_identifier_known_at",
        table_name="security_identifiers",
    )
    op.drop_index(
        "ix_security_identifier_security_valid",
        table_name="security_identifiers",
    )
    op.drop_index(
        "ix_security_identifier_lookup",
        table_name="security_identifiers",
    )
    op.drop_index(
        "ix_security_identifiers_identifier_type",
        table_name="security_identifiers",
    )
    op.drop_index(
        "ix_security_identifiers_security_id",
        table_name="security_identifiers",
    )
    op.drop_table("security_identifiers")

    op.drop_index(
        "ix_security_identifier_history_known_at",
        table_name="security_identifier_history",
    )
    op.drop_index(
        "ix_security_listing_history_effective",
        table_name="security_identifier_history",
    )
    op.drop_constraint(
        "uq_security_listing_history_revision",
        "security_identifier_history",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_security_identifier_history_identity",
        "security_identifier_history",
        ["security_id", "symbol", "exchange"],
    )
    for column in (
        "source_reference",
        "source",
        "known_at",
        "effective_to",
        "effective_from",
    ):
        op.drop_column("security_identifier_history", column)
