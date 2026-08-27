from datetime import date
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app
from quantcore.api.dependencies import get_macro_service
from quantcore.services.macro_service import MacroSyncResult


client = TestClient(app)


def test_macro_series_endpoint():
    service = Mock()
    service.get_series.return_value = Mock(
        series_id="GDP",
        title="Gross Domestic Product",
        frequency="Quarterly",
        frequency_short="Q",
        units="Billions",
        units_short="Bil.",
        seasonal_adjustment="Seasonally Adjusted",
        seasonal_adjustment_short="SA",
        observation_start=date(1947, 1, 1),
        observation_end=date(2026, 4, 1),
        last_updated=None,
    )
    app.dependency_overrides[get_macro_service] = lambda: service
    try:
        response = client.get("/macro/series/GDP")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["series_id"] == "GDP"
