from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app
from quantcore.core.enums import CorporateActionType
from quantcore.services.corporate_action_service import (
    CorporateActionSyncResult,
)


client = TestClient(app)


def test_get_corporate_actions():
    action = Mock()
    action.effective_date = date(2024, 11, 1)
    action.action_type = CorporateActionType.DIVIDEND
    action.amount = 0.25
    action.split_ratio = None

    with patch(
        "quantcore.api.dependencies.CorporateActionService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_actions.return_value = [action]

        response = client.get("/corporate-actions/AAPL")

    assert response.status_code == 200
    assert response.json() == [{
        "effective_date": "2024-11-01",
        "action_type": "DIVIDEND",
        "amount": 0.25,
        "split_ratio": None,
    }]


def test_get_corporate_actions_supports_as_of_query():
    action = Mock()
    action.effective_date = date(2024, 11, 1)
    action.action_type = CorporateActionType.DIVIDEND
    action.amount = 0.25
    action.split_ratio = None

    with patch(
        "quantcore.api.dependencies.CorporateActionService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_actions.return_value = [action]

        response = client.get(
            "/corporate-actions/AAPL",
            params={"as_of": "2025-01-01T00:00:00Z"},
        )

    assert response.status_code == 200
    service.get_actions.assert_called_once()
    assert service.get_actions.call_args.kwargs["as_of"] == datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_sync_corporate_actions():
    with patch(
        "quantcore.api.dependencies.CorporateActionService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.sync_corporate_actions.return_value = CorporateActionSyncResult(
            created=2,
            updated=1,
            unchanged=3,
            records_processed=5,
        )

        response = client.post("/corporate-actions/AAPL/sync")

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "AAPL",
        "actions_added": 2,
        "actions_updated": 1,
        "actions_unchanged": 3,
        "actions_processed": 5,
    }
