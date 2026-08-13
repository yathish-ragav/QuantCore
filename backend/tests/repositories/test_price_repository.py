from datetime import datetime
from unittest.mock import Mock

from quantcore.models.price import Price
from quantcore.repositories.price_repository import PriceRepository


def make_repository():
    db = Mock()
    repository = PriceRepository(db)

    return repository, db


def test_get_for_security_returns_prices():

    repository, db = make_repository()

    prices = [
        Mock(spec=Price),
        Mock(spec=Price),
    ]

    query = db.query.return_value
    filtered_query = query.filter.return_value
    ordered_query = filtered_query.order_by.return_value
    ordered_query.all.return_value = prices

    result = repository.get_for_security(
        security_id=1
    )

    db.query.assert_called_once_with(Price)

    query.filter.assert_called_once()

    filtered_query.order_by.assert_called_once()

    ordered_query.all.assert_called_once()

    assert result == prices


def test_get_for_security_returns_empty_list():

    repository, db = make_repository()

    query = db.query.return_value
    filtered_query = query.filter.return_value
    ordered_query = filtered_query.order_by.return_value
    ordered_query.all.return_value = []

    result = repository.get_for_security(
        security_id=999
    )

    assert result == []


def test_get_by_security_and_date_returns_price():

    repository, db = make_repository()

    price = Mock(spec=Price)

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = price

    date = datetime(
        2026,
        1,
        2,
    )

    result = repository.get_by_security_and_date(
        security_id=1,
        date=date,
    )

    db.query.assert_called_once_with(Price)

    query.filter.assert_called_once()

    filtered_query.first.assert_called_once()

    assert result == price


def test_get_by_security_and_date_returns_none():

    repository, db = make_repository()

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = None

    date = datetime(
        2026,
        1,
        2,
    )

    result = repository.get_by_security_and_date(
        security_id=1,
        date=date,
    )

    assert result is None


def test_create_price():

    repository, db = make_repository()

    date = datetime(
        2026,
        1,
        2,
    )

    price = repository.create(
        security_id=1,
        date=date,
        open=250.0,
        high=255.0,
        low=248.0,
        close=253.0,
        volume=1_000_000,
        dividends=0.0,
        stock_splits=0.0,
    )

    db.add.assert_called_once_with(price)

    assert isinstance(price, Price)

    assert price.security_id == 1
    assert price.date == date
    assert price.open == 250.0
    assert price.high == 255.0
    assert price.low == 248.0
    assert price.close == 253.0
    assert price.volume == 1_000_000
    assert price.dividends == 0.0
    assert price.stock_splits == 0.0

    # Repository must not control the transaction.
    db.commit.assert_not_called()


def test_commit():

    repository, db = make_repository()

    repository.commit()

    db.commit.assert_called_once()