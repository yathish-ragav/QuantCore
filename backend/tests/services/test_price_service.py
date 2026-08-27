from datetime import datetime, timezone
from unittest.mock import ANY, Mock

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.models.provenance import DataSource
from quantcore.schemas.price import PriceData
from quantcore.services.price_service import PriceService


def make_service():

    db = Mock()

    service = PriceService.__new__(
        PriceService
    )

    service.db = db
    service.client = Mock()
    service.client.SOURCE = "YAHOO"
    service.security_repo = Mock()
    service.price_repo = Mock()
    service.revision_repo = Mock()

    return service, db


def make_security():

    security = Mock()

    security.id = 10
    security.company_id = 1
    security.symbol = "AAPL"
    security.exchange = "NASDAQ"

    return security


def make_price_data(
    date=None,
    open=250.0,
    high=255.0,
    low=248.0,
    close=253.0,
    volume=1_000_000,
    dividends=0.0,
    stock_splits=0.0,
):

    if date is None:
        date = datetime(
            2026,
            1,
            2,
        )

    return PriceData(
        date=date,
        open=open,
        high=high,
        low=low,
        close=close,
        adjusted_close=close,
        volume=volume,
        dividends=dividends,
        stock_splits=stock_splits,
    )


def test_sync_price_history_inserts_new_prices():

    service, db = make_service()

    security = make_security()
    data = make_price_data()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        data
    ]

    service.price_repo.get_by_security_and_date.return_value = None
    created_price = Mock()
    created_price.id = 100
    created_price.date = data.date
    created_price.open = data.open
    created_price.high = data.high
    created_price.low = data.low
    created_price.close = data.close
    created_price.adjusted_close = data.adjusted_close
    created_price.price_basis = data.price_basis
    created_price.volume = data.volume
    created_price.dividends = data.dividends
    created_price.stock_splits = data.stock_splits
    created_price.source_reference = None
    service.price_repo.create.return_value = created_price
    service.revision_repo.get_next_revision_number.return_value = 1

    result = service.sync_price_history(
        "AAPL"
    )

    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0
    assert result.records_processed == 1

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_price_history.assert_called_once_with(
        "AAPL",
        period="5y",
    )

    service.price_repo.get_by_security_and_date.assert_called_once_with(
        10,
        data.date,
    )

    service.price_repo.create.assert_called_once_with(
        security_id=10,
        date=data.date,
        open=data.open,
        high=data.high,
        low=data.low,
        close=data.close,
        adjusted_close=data.adjusted_close,
        price_basis=data.price_basis,
        volume=data.volume,
        dividends=data.dividends,
        stock_splits=data.stock_splits,
        source=DataSource.YAHOO,
        fetched_at=ANY,
    )

    service.revision_repo.create.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_price_history_skips_existing_prices():

    service, db = make_service()

    security = make_security()
    data = make_price_data()

    existing_price = Mock()
    existing_price.date = data.date
    existing_price.open = data.open
    existing_price.high = data.high
    existing_price.low = data.low
    existing_price.close = data.close
    existing_price.adjusted_close = data.adjusted_close
    existing_price.price_basis = data.price_basis
    existing_price.volume = data.volume
    existing_price.dividends = data.dividends
    existing_price.stock_splits = data.stock_splits

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        data
    ]

    service.price_repo.get_by_security_and_date.return_value = (
        existing_price
    )

    result = service.sync_price_history(
        "AAPL"
    )

    assert result.created == 0
    assert result.updated == 0
    assert result.unchanged == 1
    assert result.records_processed == 1

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.price_repo.get_by_security_and_date.assert_called_once_with(
        10,
        data.date,
    )

    service.price_repo.create.assert_not_called()
    service.revision_repo.create.assert_not_called()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_price_history_security_not_found():

    service, db = make_service()

    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Security 'AAPL' not found",
    ):
        service.sync_price_history("AAPL")

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_price_history.assert_not_called()

    service.price_repo.get_by_security_and_date.assert_not_called()

    service.price_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_price_history_passes_period_to_provider():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = []

    result = service.sync_price_history(
        "AAPL",
        period="1y",
    )

    assert result.records_processed == 0
    assert result.created == 0

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_price_history.assert_called_once_with(
        "AAPL",
        period="1y",
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_price_history_normalizes_symbol():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = []

    result = service.sync_price_history(
        "  aapl  "
    )

    assert result.records_processed == 0
    assert result.created == 0

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_price_history.assert_called_once_with(
        "AAPL",
        period="5y",
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_price_history_transforms_raw_dictionary_data():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        {
            "date": datetime(
                2026,
                1,
                2,
            ),
            "open": "250.0",
            "high": "255.0",
            "low": "248.0",
            "close": "253.0",
            "adjusted_close": "253.0",
            "volume": "1000000",
            "dividends": "0.0",
            "stock_splits": "0.0",
        }
    ]

    service.price_repo.get_by_security_and_date.return_value = None

    result = service.sync_price_history(
        "AAPL"
    )

    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0
    assert result.records_processed == 1

    service.price_repo.create.assert_called_once_with(
        security_id=10,
        date=datetime(
            2026,
            1,
            2,
        ),
        open=250.0,
        high=255.0,
        low=248.0,
        close=253.0,
        adjusted_close=253.0,
        price_basis=PriceBasis.UNADJUSTED,
        volume=1_000_000,
        dividends=0.0,
        stock_splits=0.0,
        source=DataSource.YAHOO,
        fetched_at=ANY,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_price_history_cleans_price_values():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        {
            "date": datetime(
                2026,
                1,
                2,
            ),
            "open": "250",
            "high": "255",
            "low": "248",
            "close": "253",
            "adjusted_close": "253",
            "volume": "1000000",
            "dividends": "0",
            "stock_splits": "0",
        }
    ]

    service.price_repo.get_by_security_and_date.return_value = None

    service.sync_price_history("AAPL")

    created = (
        service.price_repo
        .create.call_args.kwargs
    )

    assert created["open"] == 250.0
    assert created["high"] == 255.0
    assert created["low"] == 248.0
    assert created["close"] == 253.0
    assert created["adjusted_close"] == 253.0
    assert created["price_basis"] == PriceBasis.UNADJUSTED
    assert created["volume"] == 1_000_000

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_price_history_rejects_invalid_ohlc():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        make_price_data(
            high=240.0,
            low=248.0,
        )
    ]

    with pytest.raises(
        ValueError,
        match="Invalid price data",
    ):
        service.sync_price_history("AAPL")

    service.price_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_price_history_rejects_negative_volume():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        make_price_data(
            volume=-1
        )
    ]

    with pytest.raises(
        ValueError,
        match="Invalid price data",
    ):
        service.sync_price_history("AAPL")

    service.price_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_price_history_rolls_back_on_provider_error():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.side_effect = (
        RuntimeError("provider error")
    )

    with pytest.raises(
        RuntimeError,
        match="provider error",
    ):
        service.sync_price_history("AAPL")

    service.price_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_price_history_rolls_back_on_repository_error():

    service, db = make_service()

    security = make_security()
    data = make_price_data()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_price_history.return_value = [
        data
    ]

    service.price_repo.get_by_security_and_date.return_value = None
    created_price = Mock()
    created_price.id = 100
    created_price.date = data.date
    created_price.open = data.open
    created_price.high = data.high
    created_price.low = data.low
    created_price.close = data.close
    created_price.adjusted_close = data.adjusted_close
    created_price.price_basis = data.price_basis
    created_price.volume = data.volume
    created_price.dividends = data.dividends
    created_price.stock_splits = data.stock_splits
    created_price.source_reference = None
    service.price_repo.create.return_value = created_price
    service.revision_repo.get_next_revision_number.return_value = 1

    service.price_repo.create.side_effect = (
        RuntimeError("database error")
    )

    with pytest.raises(
        RuntimeError,
        match="database error",
    ):
        service.sync_price_history("AAPL")

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_sync_price_history_rejects_empty_symbol():

    service, db = make_service()

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        service.sync_price_history("   ")

    service.security_repo.get_by_symbol.assert_not_called()

    service.client.get_price_history.assert_not_called()

    service.price_repo.create.assert_not_called()

    # Empty-symbol validation happens before the transaction
    # try/except block.
    db.commit.assert_not_called()
    db.rollback.assert_not_called()



def test_sync_price_history_updates_changed_observation_and_creates_revision():
    service, db = make_service()
    security = make_security()
    data = make_price_data(close=254.0)

    existing = Mock()
    existing.id = 42
    existing.date = data.date
    existing.open = data.open
    existing.high = data.high
    existing.low = data.low
    existing.close = 253.0
    existing.adjusted_close = 253.0
    existing.price_basis = data.price_basis
    existing.volume = data.volume
    existing.dividends = data.dividends
    existing.stock_splits = data.stock_splits
    existing.source_reference = None

    service.security_repo.get_by_symbol.return_value = security
    service.client.get_price_history.return_value = [data]
    service.price_repo.get_by_security_and_date.return_value = existing
    service.revision_repo.get_next_revision_number.return_value = 2

    result = service.sync_price_history("AAPL")

    assert result.created == 0
    assert result.updated == 1
    assert result.unchanged == 0
    assert result.records_processed == 1
    assert existing.close == 254.0
    service.revision_repo.create.assert_called_once()
    assert service.revision_repo.create.call_args.kwargs["revision_number"] == 2
    db.commit.assert_called_once()


def test_get_price_history_as_of_uses_revision_repository():
    service, db = make_service()
    security = make_security()
    revisions = [Mock(), Mock()]
    as_of = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)

    service.security_repo.get_by_symbol.return_value = security
    service.revision_repo.get_latest_for_security_as_of.return_value = revisions

    result = service.get_price_history_as_of("AAPL", as_of)

    assert result == revisions
    service.security_repo.get_by_symbol.assert_called_once_with("AAPL")
    service.revision_repo.get_latest_for_security_as_of.assert_called_once_with(10, as_of)
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

def test_get_price_history_returns_prices():

    service, db = make_service()

    security = make_security()

    prices = [
        Mock(),
        Mock(),
    ]

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.price_repo.get_for_security.return_value = (
        prices
    )

    result = service.get_price_history(
        "AAPL"
    )

    assert result == prices

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.price_repo.get_for_security.assert_called_once_with(
        10
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_price_history_normalizes_symbol():

    service, db = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.price_repo.get_for_security.return_value = []

    result = service.get_price_history(
        "  aapl  "
    )

    assert result == []

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.price_repo.get_for_security.assert_called_once_with(
        10
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_price_history_security_not_found():

    service, db = make_service()

    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Security 'AAPL' not found",
    ):
        service.get_price_history("AAPL")

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.price_repo.get_for_security.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()