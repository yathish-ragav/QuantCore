from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.services.security_listing_identity_service import SecurityListingIdentityService


def make_service():
    service = SecurityListingIdentityService.__new__(SecurityListingIdentityService)
    service.db = Mock()
    service.repository = Mock()
    return service


def make_history(security_id=10, symbol="OLD", exchange="NASDAQ"):
    history = Mock()
    history.security_id = security_id
    history.symbol = symbol
    history.exchange = exchange
    return history


def test_resolve_as_of_uses_historical_listing_and_knowledge_boundary():
    service = make_service()
    history = make_history()
    security = Mock(id=10)
    service.repository.resolve_as_of.return_value = [history]
    service.db.get.return_value = security

    known_at = datetime(2025, 5, 1, tzinfo=timezone.utc)
    result = service.resolve_as_of(
        " old ",
        effective_on=date(2025, 6, 1),
        known_at=known_at,
    )

    assert result.security is security
    assert result.history is history
    service.repository.resolve_as_of.assert_called_once_with(
        "OLD",
        effective_on=date(2025, 6, 1),
        known_at=known_at,
        exchange=None,
    )
    service.db.get.assert_called_once()


def test_resolve_as_of_can_disambiguate_by_exchange():
    service = make_service()
    history = make_history(exchange="NYSE")
    service.repository.resolve_as_of.return_value = [history]
    service.db.get.return_value = Mock(id=10)

    service.resolve_as_of(
        "ABC",
        effective_on=date(2025, 1, 1),
        known_at=datetime(2025, 2, 1),
        exchange=" nyse ",
    )

    service.repository.resolve_as_of.assert_called_once_with(
        "ABC",
        effective_on=date(2025, 1, 1),
        known_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        exchange="NYSE",
    )


def test_resolve_as_of_rejects_ambiguous_symbol():
    service = make_service()
    service.repository.resolve_as_of.return_value = [
        make_history(exchange="NYSE"),
        make_history(exchange="NASDAQ"),
    ]

    with pytest.raises(DataValidationError, match="ambiguous"):
        service.resolve_as_of(
            "ABC",
            effective_on=date(2025, 1, 1),
            known_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )


def test_resolve_as_of_rejects_missing_history_instead_of_falling_back_to_current_symbol():
    service = make_service()
    service.repository.resolve_as_of.return_value = []

    with pytest.raises(ResourceNotFoundError, match="No security listing found"):
        service.resolve_as_of(
            "OLD",
            effective_on=date(2020, 1, 1),
            known_at=datetime(2020, 2, 1, tzinfo=timezone.utc),
        )

    service.db.get.assert_not_called()


def test_resolve_security_as_of_delegates_one_shared_pit_timestamp():
    service = make_service()
    security = Mock(id=10)
    history = make_history()
    service.repository.resolve_as_of.return_value = [history]
    service.db.get.return_value = security

    as_of = datetime(2025, 6, 15, 12, 30, tzinfo=timezone.utc)

    result = service.resolve_security_as_of(" old ", as_of=as_of)

    assert result is security
    service.repository.resolve_as_of.assert_called_once_with(
        "OLD",
        effective_on=date(2025, 6, 15),
        known_at=as_of,
        exchange=None,
    )


def test_resolve_security_as_of_rejects_future_boundary():
    service = make_service()
    future = datetime(2999, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(InvalidInputError):
        service.resolve_security_as_of("OLD", as_of=future)

    service.repository.resolve_as_of.assert_not_called()
