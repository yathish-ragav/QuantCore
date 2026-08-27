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
    service.revision_repo = Mock()
    service.revision_repo.get_next_revision_number.return_value = 1
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


def test_get_actions_as_of_uses_revision_repository():
    service, _ = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.revision_repo.get_latest_for_security_as_of.return_value = [Mock()]

    from datetime import datetime, timezone
    as_of = datetime(2025, 1, 1, tzinfo=timezone.utc)

    result = service.get_actions("AAPL", as_of=as_of)

    assert result == service.revision_repo.get_latest_for_security_as_of.return_value
    service.revision_repo.get_latest_for_security_as_of.assert_called_once_with(10, as_of)


def test_sync_creates_actions():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.client.get_corporate_actions.return_value = make_actions()
    service.action_repo.get_by_identity.return_value = None

    result = service.sync_corporate_actions("AAPL")

    assert result == CorporateActionSyncResult(
        created=2,
        updated=0,
        unchanged=0,
        records_processed=2,
    )
    assert service.action_repo.create.call_count == 2
    db.commit.assert_called_once()


def test_sync_is_idempotent():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    actions = make_actions()
    service.client.get_corporate_actions.return_value = actions

    existing_actions = []
    for action in actions:
        existing = Mock()
        existing.id = len(existing_actions) + 1
        existing.security_id = 10
        existing.effective_date = action.effective_date
        existing.action_type = action.action_type
        existing.amount = action.amount
        existing.split_ratio = action.split_ratio
        existing.source = DataSource.YAHOO
        existing.source_reference = (
            f"AAPL:{action.effective_date.isoformat()}:"
            f"{action.action_type.value}"
        )
        existing_actions.append(existing)

    service.action_repo.get_by_identity.side_effect = existing_actions

    result = service.sync_corporate_actions("AAPL")

    assert result == CorporateActionSyncResult(
        created=0,
        updated=0,
        unchanged=2,
        records_processed=2,
    )
    service.action_repo.create.assert_not_called()
    db.commit.assert_called_once()


def test_sync_changed_action_creates_revision():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.client.get_corporate_actions.return_value = [
        CorporateActionData(
            effective_date=date(2024, 11, 1),
            action_type=CorporateActionType.DIVIDEND,
            amount=0.30,
        )
    ]
    existing = Mock()
    existing.id = 22
    existing.security_id = 10
    existing.effective_date = date(2024, 11, 1)
    existing.action_type = CorporateActionType.DIVIDEND
    existing.amount = 0.25
    existing.split_ratio = None
    existing.source_reference = "AAPL:2024-11-01:DIVIDEND"
    service.action_repo.get_by_identity.return_value = existing
    service.revision_repo.get_next_revision_number.return_value = 2

    result = service.sync_corporate_actions("AAPL")

    assert result == CorporateActionSyncResult(
        created=0,
        updated=1,
        unchanged=0,
        records_processed=1,
    )
    service.revision_repo.create.assert_called_once()
    assert service.revision_repo.create.call_args.kwargs["revision_number"] == 2
    assert service.revision_repo.create.call_args.kwargs["amount"] == 0.30
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
