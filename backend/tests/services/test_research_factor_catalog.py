from datetime import datetime, timezone

import pytest

from quantcore.services.research_dataset_service import (
    ResearchFeature,
    ResearchFeatureVector,
)
from quantcore.services.research_factor_catalog import (
    get_research_factor_calculators,
    get_research_factor_definitions,
)
from quantcore.services.research_factor_computation_service import (
    ResearchFactorComputationService,
)

AS_OF = datetime(2026, 8, 20, tzinfo=timezone.utc)


def feature(key: str, value: float) -> ResearchFeature:
    return ResearchFeature(
        observation_key=key,
        definition_version="1",
        observation_as_of=AS_OF,
        value_numeric=value,
        value_text=None,
        unit="ratio",
        input_fingerprint=f"fp:{key}",
        input_manifest={"source": key},
    )


def test_production_factor_registry_has_matching_definitions_and_calculators():
    service = ResearchFactorComputationService(
        get_research_factor_definitions(),
        get_research_factor_calculators(),
    )

    assert [
        (item.factor_key, item.definition_version)
        for item in service.definition_registry.definitions()
    ] == [
        ("quality_score", "1"),
        ("leverage_ratio", "1"),
    ]


def test_quality_factor_is_deterministic_and_uses_pit_features():
    service = ResearchFactorComputationService(
        get_research_factor_definitions(),
        get_research_factor_calculators(),
    )
    vector = ResearchFeatureVector(
        symbol="AAPL",
        security_id=7,
        as_of=AS_OF,
        features=(
            feature("fcf_margin", 0.20),
            feature("net_margin", 0.10),
            feature("operating_margin", 0.30),
        ),
    )

    result = service.compute_factor(
        vector,
        factor_key="quality_score",
        definition_version="1",
    )

    assert result.value_numeric == pytest.approx(0.20)
    assert result.unit == "score"
    assert result.input_manifest["calculation"]["formula"] == "arithmetic_mean"


def test_leverage_factor_exposes_pit_debt_to_equity():
    service = ResearchFactorComputationService(
        get_research_factor_definitions(),
        get_research_factor_calculators(),
    )
    vector = ResearchFeatureVector(
        symbol="AAPL",
        security_id=7,
        as_of=AS_OF,
        features=(feature("debt_to_equity", 1.75),),
    )

    result = service.compute_factor(
        vector,
        factor_key="leverage_ratio",
        definition_version="1",
    )

    assert result.value_numeric == pytest.approx(1.75)
    assert result.unit == "ratio"
