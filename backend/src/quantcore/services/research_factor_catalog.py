from __future__ import annotations

from dataclasses import dataclass

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_dataset_service import ResearchFeatureVector
from quantcore.services.research_factor_computation_service import (
    ResearchFactorValue,
)
from quantcore.services.research_factor_definition_service import (
    ResearchFactorDefinition,
)


@dataclass(frozen=True)
class _RatioMeanCalculator:
    """Compute the arithmetic mean of a fixed set of numeric ratio features."""

    factor_key: str
    definition_version: str

    def compute(
        self,
        feature_vector: ResearchFeatureVector,
        definition: ResearchFactorDefinition,
    ):
        values = tuple(feature.value_numeric for feature in feature_vector.features)
        numeric_values: list[float] = []
        for value in values:
            if value is None:
                raise InvalidInputError(
                    f"{self.factor_key} requires numeric feature values."
                )
            numeric_values.append(float(value))
        score = sum(numeric_values) / len(numeric_values)
        return ResearchFactorValue(
            factor_key=self.factor_key,
            definition_version=self.definition_version,
            symbol=feature_vector.symbol,
            security_id=feature_vector.security_id,
            as_of=feature_vector.as_of,
            value_numeric=score,
            unit=definition.unit,
            input_manifest={
                "formula": "arithmetic_mean",
                "features": [
                    {
                        "observation_key": feature.observation_key,
                        "definition_version": feature.definition_version,
                    }
                    for feature in feature_vector.features
                ],
            },
        )


@dataclass(frozen=True)
class _IdentityCalculator:
    """Expose one numeric research feature as a versioned factor."""

    factor_key: str
    definition_version: str

    def compute(
        self,
        feature_vector: ResearchFeatureVector,
        definition: ResearchFactorDefinition,
    ):
        value = feature_vector.features[0].value_numeric
        if value is None:
            raise InvalidInputError(
                f"{self.factor_key} requires a numeric feature value."
            )
        return ResearchFactorValue(
            factor_key=self.factor_key,
            definition_version=self.definition_version,
            symbol=feature_vector.symbol,
            security_id=feature_vector.security_id,
            as_of=feature_vector.as_of,
            value_numeric=float(value),
            unit=definition.unit,
            input_manifest={
                "formula": "identity",
                "feature": {
                    "observation_key": feature_vector.features[0].observation_key,
                    "definition_version": feature_vector.features[0].definition_version,
                },
            },
        )


RESEARCH_FACTOR_DEFINITIONS: tuple[ResearchFactorDefinition, ...] = (
    ResearchFactorDefinition(
        factor_key="quality_score",
        definition_version="1",
        required_feature_identities=(
            ("fcf_margin", "1"),
            ("net_margin", "1"),
            ("operating_margin", "1"),
        ),
        output_kind="numeric",
        unit="score",
        description=(
            "Arithmetic mean of PIT TTM free-cash-flow, net, and operating "
            "margins. Higher values indicate stronger profitability/quality."
        ),
    ),
    ResearchFactorDefinition(
        factor_key="leverage_ratio",
        definition_version="1",
        required_feature_identities=(("debt_to_equity", "1"),),
        output_kind="numeric",
        unit="ratio",
        description="PIT-known total debt divided by total equity.",
    ),
)

RESEARCH_FACTOR_CALCULATORS = (
    _RatioMeanCalculator("quality_score", "1"),
    _IdentityCalculator("leverage_ratio", "1"),
)


def get_research_factor_definitions() -> tuple[ResearchFactorDefinition, ...]:
    return RESEARCH_FACTOR_DEFINITIONS


def get_research_factor_calculators() -> tuple:
    return RESEARCH_FACTOR_CALCULATORS
