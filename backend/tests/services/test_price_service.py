from datetime import datetime
from unittest.mock import Mock

import pytest

from quantcore.schemas.price import PriceData
from quantcore.services.price_service import PriceService


def make_service():

    db = Mock()

    service = PriceService.__new__(
        PriceService
    )

    service.db = db
    service.client = Mock()
    service.security_repo = Mock()
    service.price_repo = Mock()

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

    service.price_repo.get_by_security_and_date.return_value = (
        None
    )

    result = service.sync_price_history(
        "AAPL"
    )

    assert result == 1

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
        volume=data.volume,
        dividends=data.dividends,
        stock_splits=data.stock_splits,
    )

    service.price_repo.commit.assert_called_once()

    db.rollback.assert_not_called()


def test_sync_price_history_skips_existing_prices():

    service, db = make_service()

    security = make_security()
    data = make_price_data()

    existing_price = Mock()

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

    assert result == 0

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.price_repo.get_by_security_and_date.assert_called_once_with(
        10,
        data.date,
    )

    service.price_repo.create.assert_not_called()

    service.price_repo.commit.assert_called_once()

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

    service.price_repo.commit.assert_not_called()

    db.rollback.assert_not_called()


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

    assert result == 0

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_price_history.assert_called_once_with(
        "AAPL",
        period="1y",
    )

    service.price_repo.commit.assert_called_once()

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

    assert result == 0

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_price_history.assert_called_once_with(
        "AAPL",
        period="5y",
    )

    service.price_repo.commit.assert_called_once()


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
            "volume": "1000000",
            "dividends": "0.0",
            "stock_splits": "0.0",
        }
    ]

    service.price_repo.get_by_security_and_date.return_value = (
        None
    )

    result = service.sync_price_history(
        "AAPL"
    )

    assert result == 1

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
        volume=1_000_000,
        dividends=0.0,
        stock_splits=0.0,
    )


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
            "volume": "1000000",
            "dividends": "0",
            "stock_splits": "0",
        }
    ]

    service.price_repo.get_by_security_and_date.return_value = (
        None
    )

    service.sync_price_history("AAPL")

    created = (
        service.price_repo
        .create.call_args.kwargs
    )

    assert created["open"] == 250.0
    assert created["high"] == 255.0
    assert created["low"] == 248.0
    assert created["close"] == 253.0
    assert created["volume"] == 1_000_000


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

    service.price_repo.commit.assert_not_called()

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

    service.price_repo.commit.assert_not_called()

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

    service.price_repo.commit.assert_not_called()

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

    service.price_repo.get_by_security_and_date.return_value = (
        None
    )

    service.price_repo.create.side_effect = (
        RuntimeError("database error")
    )

    with pytest.raises(
        RuntimeError,
        match="database error",
    ):
        service.sync_price_history("AAPL")

    db.rollback.assert_called_once()

    service.price_repo.commit.assert_not_called()


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

    service.price_repo.commit.assert_not_called()

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