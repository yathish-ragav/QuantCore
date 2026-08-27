from datetime import date, datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient

from quantcore.api.dependencies import get_macro_ingestion_orchestrator
from quantcore.api.main import app
from quantcore.services.macro_ingestion_orchestrator import (
    MacroFreshnessView,
    MacroIngestionResult,
)


client = TestClient(app)


def test_macro_ingestion_freshness_endpoint():
    service = Mock()
    service.get_freshness.return_value = [
        MacroFreshnessView(
            source="FRED",
            series_id="GDP",
            max_age_seconds=172800,
            last_attempt_at=None,
            last_success_at=None,
            last_success_vintage=None,
            last_success_records=0,
            consecutive_failures=0,
            last_error=None,
            is_fresh=False,
        )
    ]
    app.dependency_overrides[get_macro_ingestion_orchestrator] = lambda: service
    try:
        response = client.get("/macro/ingestion/freshness?series_id=GDP")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["series_id"] == "GDP"
    assert response.json()[0]["is_fresh"] is False
    service.get_freshness.assert_called_once_with(["GDP"])


def test_macro_ingestion_sync_endpoint():
    service = Mock()
    service.sync_managed.return_value = [
        MacroIngestionResult(
            series_id="GDP",
            attempted=True,
            succeeded=True,
            skipped=False,
            records_processed=5,
            vintage_date=date(2026, 8, 27),
        )
    ]
    app.dependency_overrides[get_macro_ingestion_orchestrator] = lambda: service
    try:
        response = client.post("/macro/ingestion/sync?series_id=GDP&only_stale=false")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["succeeded"] is True
    assert response.json()[0]["records_processed"] == 5
    service.sync_managed.assert_called_once_with(
        series_ids=["GDP"],
        only_stale=False,
        limit=None,
        vintage_date=None,
    )
