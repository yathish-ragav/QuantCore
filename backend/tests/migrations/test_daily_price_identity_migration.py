import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "i2j3k4l5m6n7_reconcile_daily_price_identity.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "daily_price_identity_migration", MIGRATION_PATH
)
_MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MIGRATION)


def _database():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    prices = sa.Table(
        "prices",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("security_id", sa.Integer, nullable=False),
        sa.Column("date", sa.DateTime, nullable=False),
        sa.Column("open", sa.Float),
        sa.Column("high", sa.Float),
        sa.Column("low", sa.Float),
        sa.Column("close", sa.Float),
        sa.Column("adjusted_close", sa.Float),
        sa.Column("price_basis", sa.String(10), nullable=False),
        sa.Column("volume", sa.BigInteger),
        sa.Column("dividends", sa.Float),
        sa.Column("stock_splits", sa.Float),
        sa.Column("source", sa.String(10)),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("source_reference", sa.String(1000)),
    )
    revisions = sa.Table(
        "price_observation_revisions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "price_id",
            sa.Integer,
            sa.ForeignKey("prices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("date", sa.DateTime, nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("adjusted_close", sa.Float),
        sa.Column("price_basis", sa.String(10), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.Column("dividends", sa.Float, nullable=False),
        sa.Column("stock_splits", sa.Float, nullable=False),
        sa.Column("source", sa.String(10)),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(1000)),
        sa.UniqueConstraint(
            "price_id",
            "revision_number",
            name="uq_price_observation_revision_price_revision",
        ),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE UNIQUE INDEX ix_prices_security_date "
                "ON prices (security_id, date)"
            )
        )
    return engine, prices, revisions


def _insert_price(
    connection, table, *, row_id, hour, close=10.0, fetched_hour=1, security_id=7
):
    connection.execute(
        table.insert().values(
            id=row_id,
            security_id=security_id,
            date=datetime(2024, 9, 20, hour),  # noqa: DTZ001
            open=9.0,
            high=11.0,
            low=8.0,
            close=close,
            adjusted_close=None,
            price_basis="UNADJUSTED",
            volume=100,
            dividends=0.0,
            stock_splits=0.0,
            source="MASSIVE",
            fetched_at=datetime(2026, 9, 16, fetched_hour, tzinfo=timezone.utc),
            source_reference=None,
        )
    )


def _insert_revision(connection, table, *, revision_id, price_id, hour):
    connection.execute(
        table.insert().values(
            id=revision_id,
            price_id=price_id,
            revision_number=1,
            date=datetime(2024, 9, 20, hour),  # noqa: DTZ001
            open=9.0,
            high=11.0,
            low=8.0,
            close=10.0,
            adjusted_close=None,
            price_basis="UNADJUSTED",
            volume=100,
            dividends=0.0,
            stock_splits=0.0,
            source="MASSIVE",
            known_at=datetime(2026, 9, 16, hour, tzinfo=timezone.utc),
            source_reference=None,
        )
    )


def _upgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        _MIGRATION.upgrade()


def test_postgresql_migration_locks_price_tables_before_reconciliation():
    statements = []
    connection = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        exec_driver_sql=statements.append,
    )

    _MIGRATION._lock_price_tables(connection)

    assert statements == [
        "LOCK TABLE prices, price_observation_revisions IN ACCESS EXCLUSIVE MODE"
    ]


def test_non_postgresql_migration_does_not_issue_postgresql_lock():
    statements = []
    connection = SimpleNamespace(
        dialect=SimpleNamespace(name="sqlite"),
        exec_driver_sql=statements.append,
    )

    _MIGRATION._lock_price_tables(connection)

    assert statements == []


def test_migration_merges_identical_daily_rows_and_preserves_revisions():
    engine, prices, revisions = _database()
    with engine.begin() as connection:
        _insert_price(connection, prices, row_id=1, hour=4, fetched_hour=1)
        _insert_price(connection, prices, row_id=2, hour=9, fetched_hour=2)
        _insert_revision(connection, revisions, revision_id=11, price_id=1, hour=1)
        _insert_revision(connection, revisions, revision_id=12, price_id=2, hour=2)

        _upgrade(connection)

        price_rows = connection.execute(sa.select(prices)).mappings().all()
        revision_rows = (
            connection.execute(
                sa.select(revisions).order_by(revisions.c.revision_number)
            )
            .mappings()
            .all()
        )
        index_sql = connection.scalar(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='ix_prices_security_date'"
            )
        )

        assert len(price_rows) == 1
        assert price_rows[0]["id"] == 2  # most recently fetched row is retained
        assert price_rows[0]["date"] == datetime(2024, 9, 20)  # noqa: DTZ001
        assert [
            (row["id"], row["price_id"], row["revision_number"])
            for row in revision_rows
        ] == [
            (11, 2, 1),
            (12, 2, 2),
        ]
        expected_date = datetime(2024, 9, 20)  # noqa: DTZ001
        assert all(row["date"] == expected_date for row in revision_rows)
        assert "date(date)" in index_sql.lower()

        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                prices.insert().values(
                    security_id=7,
                    date=datetime(2024, 9, 20, 12),  # noqa: DTZ001
                    open=9.0,
                    high=11.0,
                    low=8.0,
                    close=10.0,
                    adjusted_close=None,
                    price_basis="UNADJUSTED",
                    volume=100,
                    dividends=0.0,
                    stock_splits=0.0,
                )
            )
    engine.dispose()


def test_migration_deletes_midnight_duplicate_before_normalizing_keeper():
    engine, prices, revisions = _database()
    with engine.begin() as connection:
        # The newer row is retained, but an older duplicate already occupies
        # midnight under the legacy (security_id, timestamp) unique index.
        _insert_price(connection, prices, row_id=1, hour=0, fetched_hour=1)
        _insert_price(connection, prices, row_id=2, hour=9, fetched_hour=2)
        _insert_revision(connection, revisions, revision_id=11, price_id=1, hour=1)
        _insert_revision(connection, revisions, revision_id=12, price_id=2, hour=2)

        _upgrade(connection)

        price_rows = connection.execute(sa.select(prices)).mappings().all()
        revision_rows = (
            connection.execute(
                sa.select(revisions).order_by(revisions.c.revision_number)
            )
            .mappings()
            .all()
        )
        assert len(price_rows) == 1
        assert price_rows[0]["id"] == 2
        assert price_rows[0]["date"] == datetime(2024, 9, 20)  # noqa: DTZ001
        assert [(row["price_id"], row["revision_number"]) for row in revision_rows] == [
            (2, 1),
            (2, 2),
        ]
    engine.dispose()


def test_migration_aborts_on_conflicting_current_prices_without_mutating_data():
    engine, prices, _ = _database()
    with engine.begin() as connection:
        _insert_price(connection, prices, row_id=1, hour=4, close=10.0)
        _insert_price(connection, prices, row_id=2, hour=9, close=12.0)

        with pytest.raises(RuntimeError, match=r"conflicting\ current\ observations"):
            _upgrade(connection)

        assert connection.scalar(sa.select(sa.func.count()).select_from(prices)) == 2
        index_sql = connection.scalar(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='ix_prices_security_date'"
            )
        )
        assert "date, date" not in index_sql.lower()
    engine.dispose()


def test_migration_reports_all_conflicting_groups_before_mutating_data():
    engine, prices, _ = _database()
    with engine.begin() as connection:
        _insert_price(connection, prices, row_id=1, hour=4, close=10.0)
        _insert_price(connection, prices, row_id=2, hour=9, close=12.0)
        _insert_price(connection, prices, row_id=3, hour=4, close=20.0, security_id=8)
        _insert_price(connection, prices, row_id=4, hour=9, close=22.0, security_id=8)

        with pytest.raises(RuntimeError) as exc_info:
            _upgrade(connection)

        message = str(exc_info.value)
        assert "2 group(s)" in message
        assert "security_id=7, date=2024-09-20" in message
        assert "security_id=8, date=2024-09-20" in message
        assert connection.scalar(sa.select(sa.func.count()).select_from(prices)) == 4
        index_sql = connection.scalar(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='ix_prices_security_date'"
            )
        )
        assert "date, date" not in index_sql.lower()
    engine.dispose()
