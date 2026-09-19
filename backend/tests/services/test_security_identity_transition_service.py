from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.enums import CorporateActionType
from quantcore.core.exceptions import DataValidationError
from quantcore.models.corporate_action_revision import CorporateActionRevision
from quantcore.models.provenance import DataSource
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.services.security_identity_transition_service import (
    SecurityIdentityTransitionService,
)


def make_revision(**overrides):
    values = dict(
        action_id=1,
        security_id=10,
        revision_number=1,
        effective_date=date(2025, 6, 2),
        action_type=CorporateActionType.TICKER_CHANGE,
        old_symbol="OLD",
        new_symbol="NEW",
        old_exchange="NASDAQ",
        new_exchange="NASDAQ",
        source=DataSource.SEC,
        known_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        source_reference="SEC:identity:1",
    )
    values.update(overrides)
    return CorporateActionRevision(**values)


def make_service():
    db = Mock()
    service = SecurityIdentityTransitionService.__new__(SecurityIdentityTransitionService)
    service.db = db
    service.security_repo = Mock()
    service.identifier_history_repo = Mock()
    return service, db


def make_security():
    security = Mock()
    security.id = 10
    security.company_id = 7
    security.symbol = "OLD"
    security.exchange = "NASDAQ"
    return security


def make_current_history():
    return SecurityIdentifierHistory(
        security_id=10,
        symbol="OLD",
        exchange="NASDAQ",
        effective_from=date(2020, 1, 1),
        effective_to=None,
        known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
        first_seen_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
        last_seen_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        is_current=True,
    )


def test_ticker_transition_reuses_same_security_and_closes_old_identifier():
    service, db = make_service()
    security = make_security()
    current = make_current_history()
    service.security_repo.get_by_id.return_value = security
    service.security_repo.get_by_company_symbol_exchange.return_value = None
    service.identifier_history_repo.get_current.side_effect = [None, current]

    result = service.apply_revision(
        make_revision(),
        as_of=datetime(2025, 7, 1, tzinfo=timezone.utc),
    )

    assert result.applied is True
    assert security.id == 10
    assert security.symbol == "NEW"
    assert security.exchange == "NASDAQ"
    service.identifier_history_repo.close_current.assert_called_once_with(
        10,
        "OLD",
        "NASDAQ",
        effective_to=date(2025, 6, 2),
    )
    created = db.add.call_args.args[0]
    assert created.security_id == 10
    assert created.symbol == "NEW"
    assert created.effective_from == date(2025, 6, 2)
    assert created.known_at == datetime(2025, 5, 1, tzinfo=timezone.utc)


def test_exchange_transition_reuses_same_security():
    service, _ = make_service()
    security = make_security()
    current = make_current_history()
    service.security_repo.get_by_id.return_value = security
    service.security_repo.get_by_company_symbol_exchange.return_value = None
    service.identifier_history_repo.get_current.side_effect = [None, current]

    revision = make_revision(
        action_type=CorporateActionType.EXCHANGE_CHANGE,
        old_symbol="OLD",
        new_symbol="OLD",
        old_exchange="NASDAQ",
        new_exchange="NYSE",
    )

    result = service.apply_revision(
        revision,
        as_of=datetime(2025, 7, 1, tzinfo=timezone.utc),
    )

    assert result.applied is True
    assert security.symbol == "OLD"
    assert security.exchange == "NYSE"


def test_transition_is_idempotent_for_same_authoritative_revision():
    service, _ = make_service()
    security = make_security()
    target = SecurityIdentifierHistory(
        security_id=10,
        symbol="NEW",
        exchange="NASDAQ",
        effective_from=date(2025, 6, 2),
        known_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        first_seen_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        last_seen_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        is_current=True,
    )
    security.symbol = "NEW"
    service.security_repo.get_by_id.return_value = security
    service.identifier_history_repo.get_current.return_value = target

    result = service.apply_revision(
        make_revision(),
        as_of=datetime(2025, 7, 1, tzinfo=timezone.utc),
    )

    assert result.applied is False
    service.identifier_history_repo.close_current.assert_not_called()
    service.db.add.assert_not_called()


def test_transition_rejects_non_sec_provenance():
    service, _ = make_service()

    with pytest.raises(DataValidationError, match="require SEC provenance"):
        service.apply_revision(make_revision(source=DataSource.YAHOO))


def test_transition_rejects_stale_old_identity():
    service, _ = make_service()
    security = make_security()
    security.symbol = "CURRENT"
    service.security_repo.get_by_id.return_value = security
    service.identifier_history_repo.get_current.return_value = None

    with pytest.raises(DataValidationError, match="stale"):
        service.apply_revision(make_revision())


def test_transition_rejects_target_owned_by_another_security():
    service, _ = make_service()
    security = make_security()
    current = make_current_history()
    conflicting = Mock()
    conflicting.id = 99
    service.security_repo.get_by_id.return_value = security
    service.identifier_history_repo.get_current.side_effect = [None, current]
    service.security_repo.get_by_company_symbol_exchange.return_value = conflicting

    with pytest.raises(DataValidationError, match="already owned by another Security"):
        service.apply_revision(make_revision())


def test_transition_rejects_future_effective_date():
    service, _ = make_service()
    future = date(2035, 1, 1)

    with pytest.raises(DataValidationError, match="future"):
        service.apply_revision(
            make_revision(effective_date=future),
            as_of=datetime(2034, 1, 1, tzinfo=timezone.utc),
        )


def test_transition_rejects_unsupported_action_type():
    service, _ = make_service()

    with pytest.raises(DataValidationError, match="only support"):
        service.apply_revision(
            make_revision(action_type=CorporateActionType.STOCK_SPLIT)
        )
