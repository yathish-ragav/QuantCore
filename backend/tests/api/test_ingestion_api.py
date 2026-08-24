from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def test_get_ingestion_freshness():
    view = Mock()
    view.dataset.value = "balance_sheet"
    view.scope.value = "company"
    view.last_attempt_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
    view.last_success_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
    view.last_success_source = "FMP"
    view.last_success_records = 10
    view.consecutive_failures = 0
    view.last_error = None
    view.is_fresh = True

    with patch(
        "quantcore.api.dependencies.IngestionOrchestrator"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_freshness.return_value = [view]

        response = client.get("/ingestion/AAPL/freshness")

    assert response.status_code == 200
    assert response.json()[0] == {
        "dataset": "balance_sheet",
        "scope": "company",
        "last_attempt_at": "2026-08-24T00:00:00Z",
        "last_success_at": "2026-08-24T00:00:00Z",
        "last_success_source": "FMP",
        "last_success_records": 10,
        "consecutive_failures": 0,
        "last_error": None,
        "is_fresh": True,
    }
    service.get_freshness.assert_called_once_with("AAPL")


def test_get_ingestion_freshness_normalizes_symbol():
    with patch(
        "quantcore.api.dependencies.IngestionOrchestrator"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_freshness.return_value = []

        response = client.get("/ingestion/aapl/freshness")

    assert response.status_code == 200
    service.get_freshness.assert_called_once_with("AAPL")
