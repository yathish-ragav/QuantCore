from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_price(
    date=None,
    open_price=250.0,
    high=255.0,
    low=248.0,
    close=253.0,
    volume=1_000_000,
    dividends=0.0,
    stock_splits=0.0,
):
    price = Mock()

    price.date = date or datetime(
        2026,
        1,
        2,
    )

    price.open = open_price
    price.high = high
    price.low = low
    price.close = close
    price.adjusted_close = close
    price.price_basis = "UNADJUSTED"
    price.volume = volume
    price.dividends = dividends
    price.stock_splits = stock_splits

    return price


@patch(
    "quantcore.api.dependencies.PriceService"
)
def test_get_prices_returns_price_history(
    mock_service,
):
    prices = [
        make_price(),
        make_price(
            date=datetime(2026, 1, 3),
            open_price=253.0,
            high=258.0,
            low=251.0,
            close=257.0,
            volume=1_200_000,
        ),
    ]

    service = Mock()
    service.get_price_history.return_value = prices

    mock_service.return_value = service

    response = client.get(
        "/prices/AAPL"
    )

    assert response.status_code == 200

    assert response.json() == [
        {
            "date": "2026-01-02T00:00:00",
            "open": 250.0,
            "high": 255.0,
            "low": 248.0,
            "close": 253.0,
            "adjusted_close": 253.0,
            "price_basis": "UNADJUSTED",
            "volume": 1_000_000,
            "dividends": 0.0,
            "stock_splits": 0.0,
        },
        {
            "date": "2026-01-03T00:00:00",
            "open": 253.0,
            "high": 258.0,
            "low": 251.0,
            "close": 257.0,
            "adjusted_close": 257.0,
            "price_basis": "UNADJUSTED",
            "volume": 1_200_000,
            "dividends": 0.0,
            "stock_splits": 0.0,
        },
    ]

    service.get_price_history.assert_called_once_with(
        "AAPL"
    )


@patch("quantcore.api.dependencies.PriceService")
def test_get_prices_supports_as_of_query(mock_service):
    service = Mock()
    service.get_price_history_as_of.return_value = [make_price()]
    mock_service.return_value = service

    response = client.get("/prices/AAPL?as_of=2026-01-05T12:00:00Z")

    assert response.status_code == 200
    service.get_price_history_as_of.assert_called_once_with(
        "AAPL",
        datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc),
    )
    service.get_price_history.assert_not_called()


@patch("quantcore.api.dependencies.PriceService")
def test_get_prices_normalizes_lowercase_symbol(
    mock_service,
):
    service = Mock()

    service.get_price_history.return_value = [
        make_price()
    ]

    mock_service.return_value = service

    response = client.get(
        "/prices/aapl"
    )

    assert response.status_code == 200

    service.get_price_history.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.PriceService"
)
def test_get_prices_normalizes_mixed_case_symbol(
    mock_service,
):
    service = Mock()

    service.get_price_history.return_value = [
        make_price()
    ]

    mock_service.return_value = service

    response = client.get(
        "/prices/aApL"
    )

    assert response.status_code == 200

    service.get_price_history.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.PriceService"
)
def test_get_prices_returns_empty_list_when_no_prices(
    mock_service,
):
    service = Mock()

    service.get_price_history.return_value = []

    mock_service.return_value = service

    response = client.get(
        "/prices/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.get_price_history.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.PriceService"
)
def test_get_prices_preserves_dividends_and_stock_splits(
    mock_service,
):
    price = make_price(
        dividends=0.25,
        stock_splits=2.0,
    )

    service = Mock()
    service.get_price_history.return_value = [
        price
    ]

    mock_service.return_value = service

    response = client.get(
        "/prices/AAPL"
    )

    assert response.status_code == 200

    assert response.json() == [
        {
            "date": "2026-01-02T00:00:00",
            "open": 250.0,
            "high": 255.0,
            "low": 248.0,
            "close": 253.0,
            "adjusted_close": 253.0,
            "price_basis": "UNADJUSTED",
            "volume": 1_000_000,
            "dividends": 0.25,
            "stock_splits": 2.0,
        }
    ]

    service.get_price_history.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.PriceService"
)
def test_get_prices_propagates_service_error(
    mock_service,
):
    service = Mock()

    service.get_price_history.side_effect = ValueError(
        "Security 'AAPL' not found. Run security sync first."
    )

    mock_service.return_value = service

    with pytest.raises(
        ValueError,
        match="Security 'AAPL' not found",
    ):
        client.get(
            "/prices/AAPL"
        )

    service.get_price_history.assert_called_once_with(
        "AAPL"
    )