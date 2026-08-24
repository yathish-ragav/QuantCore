from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import DataValidationError
from quantcore.models.security import Security, SecurityStatus
from quantcore.repositories.security_repository import SecurityRepository


def make_repository():
    db = Mock()
    repository = SecurityRepository(db)
    return repository, db


def test_get_by_symbol_returns_active_security():
    repository, db = make_repository()
    security = Mock(spec=Security)
    db.scalars.return_value.all.return_value = [security]

    result = repository.get_by_symbol("AAPL")

    assert result == security
    db.scalars.assert_called_once()
    db.scalar.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_symbol_returns_none_when_not_found():
    repository, db = make_repository()
    db.scalars.return_value.all.return_value = []

    assert repository.get_by_symbol("UNKNOWN") is None
    db.scalars.assert_called_once()


def test_get_by_symbol_rejects_ambiguous_active_listing():
    repository, db = make_repository()
    db.scalars.return_value.all.return_value = [
        Mock(spec=Security),
        Mock(spec=Security),
    ]

    with pytest.raises(DataValidationError, match="ambiguous"):
        repository.get_by_symbol("ABC")


def test_get_by_symbols_returns_securities():
    repository, db = make_repository()
    securities = [Mock(spec=Security)]
    db.scalars.return_value.all.return_value = securities

    result = repository.get_by_symbols(["AAPL"])

    assert result == securities
    db.scalars.assert_called_once()
    db.scalars.return_value.all.assert_called_once()


def test_get_by_company_ids_returns_securities():
    repository, db = make_repository()
    securities = [Mock(spec=Security)]
    db.scalars.return_value.all.return_value = securities

    assert repository.get_by_company_ids([1]) == securities
    db.scalars.assert_called_once()


def test_get_active_by_exchanges_returns_active_securities():
    repository, db = make_repository()
    securities = [Mock(spec=Security)]
    db.scalars.return_value.all.return_value = securities

    assert repository.get_active_by_exchanges(["NASDAQ"]) == securities
    db.scalars.assert_called_once()


def test_get_by_symbols_returns_empty_for_empty_input():
    repository, db = make_repository()

    assert repository.get_by_symbols([]) == []
    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    db.query.assert_not_called()


def test_security_status_values_are_stable():
    assert SecurityStatus.ACTIVE.value == "ACTIVE"
    assert SecurityStatus.INACTIVE.value == "INACTIVE"
