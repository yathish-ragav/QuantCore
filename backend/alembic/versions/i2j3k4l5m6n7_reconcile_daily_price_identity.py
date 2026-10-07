"""Reconcile daily price identity and prevent same-day duplicates.

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6

The migration consolidates duplicate daily observations only when their current
market values agree. Revision snapshots are retained and moved to the canonical
price row. Conflicting current observations abort the migration.
"""
from collections.abc import Sequence
from datetime import date, datetime, time, timezone

import sqlalchemy as sa

from alembic import op

revision: str = "i2j3k4l5m6n7"
down_revision: str | None = "h1i2j3k4l5m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PRICE_VALUE_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "price_basis",
    "volume",
    "dividends",
    "stock_splits",
)


def _daily_price_groups(connection, prices):
    return connection.execute(
        sa.select(
            prices.c.security_id,
            sa.func.date(prices.c.date).label("trading_day"),
        )
        .group_by(prices.c.security_id, sa.func.date(prices.c.date))
        .having(sa.func.count() > 1)
        .order_by(prices.c.security_id, sa.func.date(prices.c.date))
    )


def _lock_price_tables(connection) -> None:
    """Prevent concurrent price writes while daily identities are reconciled."""
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql(
            "LOCK TABLE prices, price_observation_revisions "
            "IN ACCESS EXCLUSIVE MODE"
        )


def upgrade() -> None:
    connection = op.get_bind()
    # The migration preflights and then rewrites rows. Hold a transaction-scoped
    # PostgreSQL table lock across both phases so ingestion cannot introduce a
    # duplicate or change a revision between validation and index creation.
    _lock_price_tables(connection)
    prices = sa.Table("prices", sa.MetaData(), autoload_with=connection)
    revisions = sa.Table(
        "price_observation_revisions", sa.MetaData(), autoload_with=connection
    )

    # Preflight every duplicate group before changing anything. A conflict is
    # safer to resolve explicitly than to discard a potentially valid price.
    duplicate_groups = list(_daily_price_groups(connection, prices))
    groups_to_merge = []
    conflicts = []
    for group in duplicate_groups:
        rows = list(
            connection.execute(
                sa.select(prices)
                .where(
                    prices.c.security_id == group.security_id,
                    sa.func.date(prices.c.date) == group.trading_day,
                )
                .order_by(prices.c.id)
            ).mappings()
        )
        signatures = {
            tuple(row[column] for column in _PRICE_VALUE_COLUMNS) for row in rows
        }
        if len(signatures) != 1:
            conflicts.append(
                f"security_id={group.security_id}, date={group.trading_day}"
            )
            continue

        # Keep the most recently fetched current row, with ID as a stable tie-break.
        keeper = max(
            rows,
            key=lambda row: (
                row["fetched_at"] is not None,
                row["fetched_at"] or datetime.min.replace(tzinfo=timezone.utc),
                row["id"],
            ),
        )
        groups_to_merge.append((group, rows, keeper))

    if conflicts:
        conflict_list = "; ".join(conflicts)
        raise RuntimeError(
            "Cannot reconcile daily prices: conflicting current observations "
            f"in {len(conflicts)} group(s): {conflict_list}. "
            "Resolve these groups manually before applying the migration."
        )

    for group, rows, keeper in groups_to_merge:
        row_ids = [row["id"] for row in rows]
        trading_day = (
            date.fromisoformat(group.trading_day)
            if isinstance(group.trading_day, str)
            else group.trading_day
        )
        canonical_day = datetime.combine(trading_day, time.min)

        # Preserve every immutable revision. Reassign first, temporarily using
        # unique negative IDs to avoid collisions with existing revision numbers.
        revision_rows = list(
            connection.execute(
                sa.select(revisions)
                .where(revisions.c.price_id.in_(row_ids))
                .order_by(
                    revisions.c.known_at,
                    revisions.c.price_id,
                    revisions.c.revision_number,
                    revisions.c.id,
                )
            ).mappings()
        )
        for revision_row in revision_rows:
            connection.execute(
                sa.update(revisions)
                .where(revisions.c.id == revision_row["id"])
                .values(
                    price_id=keeper["id"],
                    revision_number=-revision_row["id"],
                    date=canonical_day,
                )
            )
        for revision_number, revision_row in enumerate(revision_rows, start=1):
            connection.execute(
                sa.update(revisions)
                .where(revisions.c.id == revision_row["id"])
                .values(revision_number=revision_number)
            )

        duplicate_ids = [row_id for row_id in row_ids if row_id != keeper["id"]]
        if duplicate_ids:
            # Remove same-day rows before normalizing the keeper. The legacy
            # timestamp-level unique index may already contain a midnight row.
            connection.execute(
                sa.delete(prices).where(prices.c.id.in_(duplicate_ids))
            )

        connection.execute(
            sa.update(prices)
            .where(prices.c.id == keeper["id"])
            .values(date=canonical_day)
        )

    # Drop the timestamp-level index and enforce one observation per security
    # and calendar date, even if a future writer supplies a non-midnight time.
    op.drop_index("ix_prices_security_date", table_name="prices")
    op.create_index(
        "ix_prices_security_date",
        "prices",
        ["security_id", sa.text("(date(date))")],
        unique=True,
    )


def downgrade() -> None:
    """Restore timestamp-level uniqueness (consolidated rows are not recreated)."""
    op.drop_index("ix_prices_security_date", table_name="prices")
    op.create_index(
        "ix_prices_security_date",
        "prices",
        ["security_id", "date"],
        unique=True,
    )
