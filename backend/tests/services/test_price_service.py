from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from quantcore.services.price_service import PriceService


def make_service():

    db = Mock()

    with patch(
        "quantcore.services.price_service.ProviderFactory"
    ) as factory:

        provider = Mock()

        factory.get_provider.return_value = provider

        service = PriceService.__new__(
            PriceService
        )

        service.db = db
        service.client = provider
        service.security_repo = Mock()
        service.price_repo = Mock()

    return service, db, provider


def make_security():

    security = Mock()

    security.id = 10
    security.company_id = 1
    security.symbol = "AAPL"
    security.exchange = "NASDAQ"

    return security


def make_price_data():

    data = Mock()

    data.date = datetime(
        2026,
        1,
        2,
    )

    data.open = 250.0
    data.high = 255.0
    data.low = 248.0
    data.close = 253.0
    data.volume = 1_000_000
    data.dividends = 0.0
    data.stock_splits = 0.0

    return data


def test_sync_price_history_inserts_new_prices():

    service, db, provider = make_service()

    security = make_security()
    data = make_price_data()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    provider.get_price_history.return_value = [
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

    provider.get_price_history.assert_called_once_with(
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


def test_sync_price_history_skips_existing_prices():

    service, db, provider = make_service()

    security = make_security()
    data = make_price_data()

    existing_price = Mock()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    provider.get_price_history.return_value = [
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


def test_sync_price_history_security_not_found():

    service, db, provider = make_service()

    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Security 'AAPL' not found",
    ):
        service.sync_price_history("AAPL")

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    provider.get_price_history.assert_not_called()

    service.price_repo.get_by_security_and_date.assert_not_called()

    service.price_repo.create.assert_not_called()

    service.price_repo.commit.assert_not_called()


def test_sync_price_history_passes_period_to_provider():

    service, db, provider = make_service()

    security = make_security()

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    provider.get_price_history.return_value = []

    result = service.sync_price_history(
        "AAPL",
        period="1y",
    )

    assert result == 0

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    provider.get_price_history.assert_called_once_with(
        "AAPL",
        period="1y",
    )

    service.price_repo.commit.assert_called_once()


def test_get_price_history_returns_prices():

    service, db, provider = make_service()

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


def test_get_price_history_security_not_found():

    service, db, provider = make_service()

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