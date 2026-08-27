from datetime import date
from unittest.mock import Mock

import pytest

from quantcore.core.enums import CorporateActionType
from quantcore.models.provenance import DataSource
from quantcore.schemas.corporate_action import CorporateActionData
from quantcore.services.corporate_action_service import (
    CorporateActionService,
    CorporateActionSyncResult,
)


def make_security():
    security = Mock()
    security.id = 10
    security.symbol = "AAPL"
    return security


def make_service():
    db = Mock()
    service = CorporateActionService.__new__(CorporateActionService)
    service.db = db
    service.client = Mock()
    service.client.SOURCE = "YAHOO"
    service.security_repo = Mock()
    service.action_repo = Mock()
    return service, db


def make_actions():
    return [
        CorporateActionData(
            effective_date=date(2024, 8, 12),
            action_type=CorporateActionType.STOCK_SPLIT,
            split_ratio=4.0,
        ),
        CorporateActionData(
            effective_date=date(2024, 11, 1),
            action_type=CorporateActionType.DIVIDEND,
            amount=0.25,
        ),
    ]


def test_sync_creates_actions():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.client.get_corporate_actions.return_value = make_actions()
    service.action_repo.get_by_identity.return_value = None

    result = service.sync_corporate_actions("AAPL")

    assert result == CorporateActionSyncResult(
        created=2,
        unchanged=0,
        records_processed=2,
    )
    assert service.action_repo.create.call_count == 2
    db.commit.assert_called_once()


def test_sync_is_idempotent():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.client.get_corporate_actions.return_value = make_actions()
    service.action_repo.get_by_identity.return_value = Mock()

    result = service.sync_corporate_actions("AAPL")

    assert result == CorporateActionSyncResult(
        created=0,
        unchanged=2,
        records_processed=2,
    )
    service.action_repo.create.assert_not_called()
    db.commit.assert_called_once()


def test_sync_rolls_back_on_provider_error():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.client.get_corporate_actions.side_effect = RuntimeError("provider error")

    with pytest.raises(RuntimeError, match="provider error"):
        service.sync_corporate_actions("AAPL")

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_stamps_provenance():
    service, _ = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.client.get_corporate_actions.return_value = make_actions()
    service.action_repo.get_by_identity.return_value = None

    service.sync_corporate_actions("AAPL")

    kwargs = service.action_repo.create.call_args.kwargs
    assert kwargs["source"] is DataSource.YAHOO
    assert kwargs["source_reference"].startswith("AAPL:")
