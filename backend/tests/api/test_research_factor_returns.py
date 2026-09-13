from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.core.enums import PriceBasis
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_factor_panel_service import (
    ResearchFactorPanel,
    ResearchFactorPanelRow,
)
from quantcore.services.research_factor_return_service import (
    ResearchFactorReturnPanel,
    ResearchFactorReturnRow,
)
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalDataset,
    ResearchHistoricalDatasetRow,
)


client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_factor_return_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_dataset():
    from quantcore.services.research_dataset_service import ResearchFeatureVector

    vector = ResearchFeatureVector(
        symbol="AAPL",
        security_id=42,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        features=(),
    )
    row = ResearchHistoricalDatasetRow(
        symbol="AAPL",
        security_id=42,
        as_of=vector.as_of,
        feature_vector=vector,
    )
    return ResearchHistoricalDataset(
        rows=(row,),
        definition_identities=(("roe", "1"),),
        dataset_identity=("quality-dataset", "1"),
    )


def make_panel():
    factor_value = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol="AAPL",
        security_id=42,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        value_numeric=0.25,
        unit="score",
        input_manifest={"source": "test"},
    )
    return ResearchFactorPanel(
        factor_key="quality_score",
        definition_version="1",
        rows=(
            ResearchFactorPanelRow(
                symbol="AAPL",
                security_id=42,
                as_of=factor_value.as_of,
                factor_value=factor_value,
            ),
        ),
        unit="score",
    )


def make_ranked_panel():
    panel = make_panel()
    row = panel.rows[0]
    return ResearchFactorRankedPanel(
        factor_key=panel.factor_key,
        definition_version=panel.definition_version,
        rows=(
            ResearchFactorRankRow(
                symbol=row.symbol,
                security_id=row.security_id,
                as_of=row.as_of,
                factor_value=row.factor_value,
                rank=1.0,
                normalized_rank=0.5,
            ),
        ),
        ranking="average_tie",
        higher_is_better=True,
    )


def make_return_panel():
    ranked_row = make_ranked_panel().rows[0]
    return ResearchFactorReturnPanel(
        factor_key="quality_score",
        definition_version="1",
        horizon=1,
        return_price_basis=PriceBasis.UNADJUSTED,
        entry_policy="NEXT_AVAILABLE_PRICE_AFTER_FACTOR_AS_OF",
        rows=(
            ResearchFactorReturnRow(
                symbol="AAPL",
                security_id=42,
                factor_as_of=ranked_row.as_of,
                factor_value=ranked_row.factor_value,
                factor_rank=ranked_row.rank,
                normalized_rank=ranked_row.normalized_rank,
                horizon=1,
                entry_date=datetime(2026, 8, 21, tzinfo=timezone.utc),
                exit_date=datetime(2026, 8, 22, tzinfo=timezone.utc),
                entry_price=100.0,
                exit_price=110.0,
                forward_return=0.1,
                return_price_basis=PriceBasis.UNADJUSTED,
                status="AVAILABLE",
            ),
        ),
    )


@dataclass
class Price:
    date: datetime
    close: float
    adjusted_close: float | None


def test_build_research_factor_returns_returns_stable_contract():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory, patch(
        "quantcore.api.dependencies.get_research_factor_computation_service"
    ), patch(
        "quantcore.api.dependencies.ResearchFactorPanelService"
    ) as panel_factory, patch(
        "quantcore.api.dependencies.ResearchFactorCrossSectionalService"
    ) as ranking_factory, patch(
        "quantcore.api.dependencies.ResearchFactorReturnService"
    ) as return_factory, patch(
        "quantcore.api.dependencies.PriceService"
    ) as price_factory:
        historical_service = Mock()
        historical_service.build_historical_dataset.return_value = make_dataset()
        historical_factory.return_value = historical_service

        panel_service = Mock()
        panel_service.build_factor_panel.return_value = make_panel()
        panel_factory.return_value = panel_service

        ranking_service = Mock()
        ranking_service.rank_factor_panel.return_value = make_ranked_panel()
        ranking_factory.return_value = ranking_service

        return_service = Mock()
        return_service.compute_forward_returns.return_value = make_return_panel()
        return_factory.return_value = return_service

        price_service = Mock()
        price_service.get_price_history.return_value = (
            Price(datetime(2026, 8, 21, tzinfo=timezone.utc), 100.0, 100.0),
            Price(datetime(2026, 8, 22, tzinfo=timezone.utc), 110.0, 110.0),
        )
        price_factory.return_value = price_service

        response = client.post(
            "/api/v1/research/factors/returns",
            json={
                "symbols": ["aapl"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "definition_identities": [["roe", "1"]],
                "dataset_identity": ["quality-dataset", "1"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 1,
                "higher_is_better": True,
                "return_price_basis": "UNADJUSTED",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["factor_key"] == "quality_score"
    assert body["definition_version"] == "1"
    assert body["dataset_identity"] == ["quality-dataset", "1"]
    assert len(body["dataset_fingerprint"]) == 64
    assert body["horizon"] == 1
    assert body["return_price_basis"] == "UNADJUSTED"
    assert body["ranking"] == "average_tie"
    assert body["higher_is_better"] is True
    assert body["row_count"] == 1
    assert body["rows"][0]["factor_rank"] == 1.0
    assert body["rows"][0]["forward_return"] == 0.1
    assert body["rows"][0]["status"] == "AVAILABLE"
    ranking_service.rank_factor_panel.assert_called_once()
    price_service.get_price_history.assert_called_once_with("AAPL")
    return_service.compute_forward_returns.assert_called_once()


def test_research_factor_returns_rejects_oversized_row_request():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory:
        historical_factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/factors/returns",
            json={
                "symbols": [f"SYM{i}" for i in range(100)],
                "as_ofs": [
                    f"2026-08-{day:02d}T15:30:00Z"
                    for day in range(1, 12)
                ],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 1,
            },
        )

    assert response.status_code == 400


def test_research_factor_returns_require_return_parameters():
    response = client.post(
        "/api/v1/research/factors/returns",
        json={
            "symbols": ["AAPL"],
            "as_ofs": ["2026-08-20T15:30:00Z"],
            "factor_key": "quality_score",
            "factor_definition_version": "1",
        },
    )
    assert response.status_code == 422


def test_research_factor_returns_rejects_invalid_horizon():
    response = client.post(
        "/api/v1/research/factors/returns",
        json={
            "symbols": ["AAPL"],
            "as_ofs": ["2026-08-20T15:30:00Z"],
            "factor_key": "quality_score",
            "factor_definition_version": "1",
            "horizon": 0,
        },
    )
    assert response.status_code == 422


def test_research_factor_returns_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/factors/returns",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 1,
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_research_factor_returns_reject_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.post(
            "/api/v1/research/factors/returns",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 1,
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_factor_return_route_is_in_openapi():
    assert "/api/v1/research/factors/returns" in app.openapi()["paths"]
