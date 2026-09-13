from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_return_methodology_service import (
    ResearchFactorReturnSeries,
    ResearchFactorReturnSlice,
    ResearchFactorReturnBucket,
)
from quantcore.core.enums import PriceBasis
from quantcore.services.research_factor_return_service import ResearchFactorReturnPanel
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
def _authenticated_research_factor_return_methodology_api():
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


def make_return_panel():
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
    from quantcore.services.research_factor_return_service import ResearchFactorReturnRow

    row = ResearchFactorReturnRow(
        symbol="AAPL",
        security_id=42,
        factor_as_of=factor_value.as_of,
        factor_value=factor_value,
        factor_rank=1.0,
        normalized_rank=0.5,
        horizon=5,
        entry_date=datetime(2026, 8, 21, tzinfo=timezone.utc),
        exit_date=datetime(2026, 8, 28, tzinfo=timezone.utc),
        entry_price=100.0,
        exit_price=110.0,
        forward_return=0.1,
        return_price_basis=PriceBasis.UNADJUSTED,
        status="AVAILABLE",
    )
    return ResearchFactorReturnPanel(
        factor_key="quality_score",
        definition_version="1",
        horizon=5,
        return_price_basis=PriceBasis.UNADJUSTED,
        entry_policy="NEXT_AVAILABLE_PRICE_AFTER_FACTOR_AS_OF",
        rows=(row,),
    )


def make_series():
    bucket = ResearchFactorReturnBucket(1, 1, 1, 0.1)
    slice_ = ResearchFactorReturnSlice(
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        total_observation_count=1,
        eligible_observation_count=1,
        long_bucket=1,
        short_bucket=2,
        long_return=0.1,
        short_return=-0.02,
        long_short_return=0.12,
        status="AVAILABLE",
        buckets=(bucket, ResearchFactorReturnBucket(2, 0, 0, None)),
    )
    return ResearchFactorReturnSeries(
        factor_key="quality_score",
        definition_version="1",
        horizon=5,
        return_price_basis=PriceBasis.UNADJUSTED,
        bucket_count=2,
        weighting="EQUAL_WEIGHTED",
        long_bucket=1,
        short_bucket=2,
        construction="RANK_ORDERED_BUCKET_LONG_SHORT",
        slices=(slice_,),
    )


def test_build_research_factor_return_series_returns_stable_contract():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory, patch(
        "quantcore.api.dependencies.ResearchFactorPanelService"
    ) as panel_factory, patch(
        "quantcore.api.dependencies.ResearchFactorCrossSectionalService"
    ) as cross_sectional_factory, patch(
        "quantcore.api.dependencies.ResearchFactorReturnService"
    ) as return_factory, patch(
        "quantcore.api.dependencies.ResearchFactorReturnMethodologyService"
    ) as methodology_factory, patch(
        "quantcore.api.dependencies.PriceService"
    ) as price_factory:
        historical_service = Mock()
        historical_service.build_historical_dataset.return_value = make_dataset()
        historical_factory.return_value = historical_service

        panel_service = Mock()
        panel_service.build_factor_panel.return_value = Mock()
        panel_factory.return_value = panel_service

        cross_sectional_service = Mock()
        ranked_panel = Mock()
        ranked_panel.rows = ()
        ranked_panel.ranking = "average_tie"
        ranked_panel.higher_is_better = True
        cross_sectional_service.rank_factor_panel.return_value = ranked_panel
        cross_sectional_factory.return_value = cross_sectional_service

        return_service = Mock()
        return_service.compute_forward_returns.return_value = make_return_panel()
        return_factory.return_value = return_service

        methodology_service = Mock()
        methodology_service.compute_factor_return_series.return_value = make_series()
        methodology_factory.return_value = methodology_service

        price_service = Mock()
        price_factory.return_value = price_service

        response = client.post(
            "/api/v1/research/factors/returns/series",
            json={
                "symbols": ["aapl"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "definition_identities": [["roe", "1"]],
                "dataset_identity": ["quality-dataset", "1"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 5,
                "higher_is_better": True,
                "return_price_basis": "UNADJUSTED",
                "bucket_count": 2,
                "minimum_observations_per_leg": 1,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["factor_key"] == "quality_score"
    assert body["dataset_identity"] == ["quality-dataset", "1"]
    assert len(body["dataset_fingerprint"]) == 64
    assert body["bucket_count"] == 2
    assert body["weighting"] == "EQUAL_WEIGHTED"
    assert body["row_count"] == 1
    assert body["slices"][0]["long_short_return"] == pytest.approx(0.12)
    assert len(body["slices"][0]["buckets"]) == 2
    historical_service.build_historical_dataset.assert_called_once_with(
        ["aapl"],
        as_ofs=[datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)],
        definition_identities=[("roe", "1")],
        dataset_identity=("quality-dataset", "1"),
    )
    methodology_service.compute_factor_return_series.assert_called_once_with(
        return_service.compute_forward_returns.return_value,
        bucket_count=2,
        minimum_observations_per_leg=1,
    )


def test_research_factor_return_methodology_rejects_oversized_request():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory:
        historical_factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/factors/returns/series",
            json={
                "symbols": [f"SYM{i}" for i in range(100)],
                "as_ofs": [
                    f"2026-08-{day:02d}T15:30:00Z"
                    for day in range(1, 12)
                ],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 5,
                "bucket_count": 5,
                "minimum_observations_per_leg": 1,
            },
        )

    assert response.status_code == 400


def test_research_factor_return_methodology_requires_methodology_parameters():
    response = client.post(
        "/api/v1/research/factors/returns/series",
        json={
            "symbols": ["AAPL"],
            "as_ofs": ["2026-08-20T15:30:00Z"],
            "factor_key": "quality_score",
            "factor_definition_version": "1",
            "horizon": 5,
        },
    )
    assert response.status_code == 422


def test_research_factor_return_methodology_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/factors/returns/series",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 5,
                "bucket_count": 5,
                "minimum_observations_per_leg": 1,
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_research_factor_return_methodology_rejects_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.post(
            "/api/v1/research/factors/returns/series",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "horizon": 5,
                "bucket_count": 5,
                "minimum_observations_per_leg": 1,
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_factor_return_methodology_route_is_in_openapi():
    assert "/api/v1/research/factors/returns/series" in app.openapi()["paths"]
