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

    db.scalars.return_value.all.return_value = prices

    result = repository.get_for_security(
        security_id=1
    )

    db.scalars.assert_called_once()

    db.scalars.return_value.all.assert_called_once()

    assert result == prices


def test_get_for_security_returns_empty_list():

    repository, db = make_repository()

    db.scalars.return_value.all.return_value = []

    result = repository.get_for_security(
        security_id=999
    )

    db.scalars.assert_called_once()

    db.scalars.return_value.all.assert_called_once()

    assert result == []


def test_get_by_security_and_date_returns_price():

    repository, db = make_repository()

    price = Mock(spec=Price)

    db.scalar.return_value = price

    date = datetime(
        2026,
        1,
        2,
    )

    result = repository.get_by_security_and_date(
        security_id=1,
        date=date,
    )

    db.scalar.assert_called_once()

    assert result == price


def test_get_by_security_and_date_returns_none():

    repository, db = make_repository()

    db.scalar.return_value = None

    date = datetime(
        2026,
        1,
        2,
    )

    result = repository.get_by_security_and_date(
        security_id=1,
        date=date,
    )

    db.scalar.assert_called_once()

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
    db.rollback.assert_not_called()