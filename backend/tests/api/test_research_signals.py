from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_dataset_service import ResearchFeatureVector
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalDataset,
    ResearchHistoricalDatasetRow,
)
from quantcore.services.research_signal_service import (
    ResearchSignalContribution,
    ResearchSignalDefinition,
    ResearchSignalPanel,
    ResearchSignalRow,
)

client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_signal_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_dataset():
    vector = ResearchFeatureVector(
        symbol="AAA",
        security_id=1,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        features=(),
    )
    row = ResearchHistoricalDatasetRow(
        symbol="AAA",
        security_id=1,
        as_of=vector.as_of,
        feature_vector=vector,
    )
    return ResearchHistoricalDataset(
        rows=(row,),
        definition_identities=(("roe", "1"),),
        dataset_identity=("quality-dataset", "1"),
    )


def make_ranked_panel(factor_key, version, normalized_ranks):
    rows = []
    for security_id, symbol, normalized_rank in normalized_ranks:
        value = ResearchFactorValue(
            factor_key=factor_key,
            definition_version=version,
            symbol=symbol,
            security_id=security_id,
            as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
            value_numeric=normalized_rank,
        )
        rows.append(
            ResearchFactorRankRow(
                symbol=symbol,
                security_id=security_id,
                as_of=value.as_of,
                factor_value=value,
                rank=1.0 if normalized_rank == 1.0 else 2.0,
                normalized_rank=normalized_rank,
            )
        )
    return ResearchFactorRankedPanel(
        factor_key=factor_key,
        definition_version=version,
        ranking="average_tie",
        higher_is_better=True,
        rows=tuple(rows),
    )


def make_signal():
    return ResearchSignalPanel(
        signal_key="quality_momentum",
        definition_version="1",
        factor_identities=(("quality", "1"), ("momentum", "1")),
        construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
        rows=(
            ResearchSignalRow(
                symbol="AAA",
                security_id=1,
                as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
                score=0.75,
                centered_score=0.5,
                contributions=(
                    ResearchSignalContribution(
                        factor_key="quality",
                        definition_version="1",
                        normalized_rank=1.0,
                        weight=0.5,
                        weighted_contribution=0.5,
                    ),
                    ResearchSignalContribution(
                        factor_key="momentum",
                        definition_version="1",
                        normalized_rank=0.5,
                        weight=0.5,
                        weighted_contribution=0.25,
                    ),
                ),
            ),
        ),
    )


def test_build_research_signal_returns_stable_contract():
    with patch("quantcore.api.dependencies.ResearchHistoricalAnalysisService") as historical_factory,         patch("quantcore.api.dependencies.ResearchFactorPanelService") as panel_factory,         patch("quantcore.api.dependencies.ResearchFactorCrossSectionalService") as cross_factory,         patch("quantcore.api.dependencies.ResearchSignalService") as signal_factory:
        historical_service = Mock()
        historical_service.build_historical_dataset.return_value = make_dataset()
        historical_factory.return_value = historical_service

        panel_service = Mock()
        panel_service.build_factor_panel.side_effect = [
            Mock(),
            Mock(),
        ]
        panel_factory.return_value = panel_service

        cross_service = Mock()
        cross_service.rank_factor_panel.side_effect = [
            make_ranked_panel("quality", "1", [(1, "AAA", 1.0), (2, "BBB", 0.0)]),
            make_ranked_panel("momentum", "1", [(1, "AAA", 0.5), (2, "BBB", 0.5)]),
        ]
        cross_factory.return_value = cross_service

        signal_service = Mock()
        signal_service.construct_signal.return_value = make_signal()
        signal_factory.return_value = signal_service

        response = client.post(
            "/api/v1/research/signals",
            json={
                "symbols": ["aaa"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "definition_identities": [["roe", "1"]],
                "dataset_identity": ["quality-dataset", "1"],
                "signal_key": "quality_momentum",
                "signal_definition_version": "1",
                "description": "Quality plus momentum",
                "factors": [
                    {"factor_key": "quality", "definition_version": "1", "weight": 0.5, "higher_is_better": True},
                    {"factor_key": "momentum", "definition_version": "1", "weight": 0.5, "higher_is_better": False},
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["signal_key"] == "quality_momentum"
    assert body["definition_version"] == "1"
    assert body["description"] == "Quality plus momentum"
    assert len(body["dataset_fingerprint"]) == 64
    assert body["factor_count"] == 2
    assert body["construction"] == "WEIGHTED_NORMALIZED_RANK_AVERAGE"
    assert body["row_count"] == 1
    assert body["rows"][0]["score"] == pytest.approx(0.75)
    assert body["factors"][1]["higher_is_better"] is False
    assert len(body["rows"][0]["contributions"]) == 2
    assert body["rows"][0]["contributions"][0]["weighted_contribution"] == pytest.approx(0.5)

    assert historical_service.build_historical_dataset.called
    assert panel_service.build_factor_panel.call_count == 2
    assert cross_service.rank_factor_panel.call_count == 2
    signal_service.construct_signal.assert_called_once()
    definition = signal_service.construct_signal.call_args.args[0]
    panels = signal_service.construct_signal.call_args.args[1]
    assert isinstance(definition, ResearchSignalDefinition)
    assert definition.identity == ("quality_momentum", "1")
    assert definition.factor_identities == (("quality", "1"), ("momentum", "1"))
    assert definition.weights == (0.5, 0.5)
    assert set(panels) == {("quality", "1"), ("momentum", "1")}


def test_research_signal_rejects_oversized_request():
    with patch("quantcore.api.dependencies.ResearchHistoricalAnalysisService") as historical_factory:
        historical_factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/signals",
            json={
                "symbols": [f"SYM{i}" for i in range(100)],
                "as_ofs": [f"2026-08-{day:02d}T15:30:00Z" for day in range(1, 12)],
                "signal_key": "x",
                "signal_definition_version": "1",
                "factors": [{"factor_key": "quality", "definition_version": "1", "weight": 1.0}],
            },
        )
    assert response.status_code == 400
    historical_factory.return_value.build_historical_dataset.assert_not_called()


def test_research_signal_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/signals",
            json={
                "symbols": ["AAA"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "signal_key": "x",
                "signal_definition_version": "1",
                "factors": [{"factor_key": "quality", "definition_version": "1", "weight": 1.0}],
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401


def test_research_signal_requires_factors():
    response = client.post(
        "/api/v1/research/signals",
        json={
            "symbols": ["AAA"],
            "as_ofs": ["2026-08-20T15:30:00Z"],
            "signal_key": "x",
            "signal_definition_version": "1",
            "factors": [],
        },
    )
    assert response.status_code == 422
