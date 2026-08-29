from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_dataset_service import ResearchFeature, ResearchFeatureVector
from quantcore.services.research_factor_computation_service import (
    ResearchFactorComputationService,
    ResearchFactorValue,
)


AS_OF = datetime(2026, 8, 20, tzinfo=timezone.utc)


class QualityCalculator:
    factor_key = "quality_score"
    definition_version = "1"

    def compute(self, feature_vector, definition):
        net_margin, operating_margin = feature_vector.features
        return ResearchFactorValue(
            factor_key=self.factor_key,
            definition_version=self.definition_version,
            symbol=feature_vector.symbol,
            security_id=feature_vector.security_id,
            as_of=feature_vector.as_of,
            value_numeric=(
                float(net_margin.value_numeric)
                + float(operating_margin.value_numeric)
            )
            / 2,
            unit=definition.unit,
            input_manifest={"formula": "mean(net_margin, operating_margin)"},
        )


class TextCalculator:
    factor_key = "quality_label"
    definition_version = "1"

    def compute(self, feature_vector, definition):
        return ResearchFactorValue(
            factor_key=self.factor_key,
            definition_version=self.definition_version,
            symbol=feature_vector.symbol,
            security_id=feature_vector.security_id,
            as_of=feature_vector.as_of,
            value_text="strong",
            unit=None,
        )


def feature(key, version, *, numeric=1.0, as_of=AS_OF, fingerprint="fp"):
    return ResearchFeature(
        observation_key=key,
        definition_version=version,
        observation_as_of=as_of,
        value_numeric=numeric,
        value_text=None,
        unit="ratio",
        input_fingerprint=fingerprint,
        input_manifest={"source": key},
    )


def vector(*features, symbol="AAPL", security_id=7, as_of=AS_OF):
    return ResearchFeatureVector(
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        features=tuple(features),
    )


def service(definition=None, calculator=None):
    definition = definition or {
        "factor_key": "quality_score",
        "definition_version": "1",
        "required_feature_identities": (
            ("net_margin", "1"),
            ("operating_margin", "1"),
        ),
        "output_kind": "numeric",
        "unit": "score",
    }
    from quantcore.services.research_factor_definition_service import ResearchFactorDefinition

    return ResearchFactorComputationService(
        (ResearchFactorDefinition(**definition),),
        (calculator or QualityCalculator(),),
    )


def test_compute_factor_uses_versioned_definition_and_preserves_pit_provenance():
    result = service().compute_factor(
        vector(feature("net_margin", "1", numeric=0.2), feature("operating_margin", "1", numeric=0.4)),
        factor_key=" quality_score ",
        definition_version=" 1 ",
    )

    assert result.value_numeric == pytest.approx(0.3)
    assert (result.factor_key, result.definition_version) == ("quality_score", "1")
    assert result.symbol == "AAPL"
    assert result.security_id == 7
    assert result.as_of == AS_OF
    assert result.input_manifest["pit_dataset"]["as_of"] == AS_OF.isoformat()
    assert len(result.input_manifest["inputs"]) == 2
    assert result.input_manifest["inputs"][0]["input_fingerprint"] == "fp"


def test_compute_factor_requires_exact_feature_identity_order():
    with pytest.raises(InvalidInputError):
        service().compute_factor(
            vector(
                feature("operating_margin", "1"),
                feature("net_margin", "1"),
            ),
            factor_key="quality_score",
            definition_version="1",
        )


def test_compute_factor_rejects_missing_feature():
    with pytest.raises(InvalidInputError):
        service().compute_factor(
            vector(feature("net_margin", "1")),
            factor_key="quality_score",
            definition_version="1",
        )


def test_compute_factor_rejects_duplicate_feature_identity():
    with pytest.raises(InvalidInputError):
        service().compute_factor(
            vector(
                feature("net_margin", "1"),
                feature("net_margin", "1", fingerprint="fp2"),
            ),
            factor_key="quality_score",
            definition_version="1",
        )


def test_compute_factor_rejects_feature_after_as_of_boundary():
    future = AS_OF.replace(hour=12)
    with pytest.raises(InvalidInputError):
        service().compute_factor(
            vector(
                feature("net_margin", "1"),
                feature("operating_margin", "1", as_of=future),
            ),
            factor_key="quality_score",
            definition_version="1",
        )


def test_compute_factor_rejects_unknown_definition():
    with pytest.raises(ResourceNotFoundError):
        service().compute_factor(
            vector(feature("net_margin", "1"), feature("operating_margin", "1")),
            factor_key="unknown",
            definition_version="1",
        )


def test_compute_factor_rejects_missing_calculator():
    from quantcore.services.research_factor_definition_service import ResearchFactorDefinition

    definition = ResearchFactorDefinition(
        factor_key="other_factor",
        definition_version="1",
        required_feature_identities=(("net_margin", "1"),),
        output_kind="numeric",
        unit="score",
    )
    with pytest.raises(ResourceNotFoundError):
        ResearchFactorComputationService((definition,), (QualityCalculator(),))


def test_compute_factor_validates_output_kind_and_unit():
    class BadCalculator(QualityCalculator):
        def compute(self, feature_vector, definition):
            result = super().compute(feature_vector, definition)
            return ResearchFactorValue(
                factor_key=result.factor_key,
                definition_version=result.definition_version,
                symbol=result.symbol,
                security_id=result.security_id,
                as_of=result.as_of,
                value_text="wrong",
                unit=result.unit,
            )

    with pytest.raises(InvalidInputError):
        service(calculator=BadCalculator()).compute_factor(
            vector(feature("net_margin", "1"), feature("operating_margin", "1")),
            factor_key="quality_score",
            definition_version="1",
        )


def test_compute_factor_supports_text_output_without_unit():
    from quantcore.services.research_factor_definition_service import ResearchFactorDefinition

    definition = ResearchFactorDefinition(
        factor_key="quality_label",
        definition_version="1",
        required_feature_identities=(("net_margin", "1"),),
        output_kind="text",
        unit=None,
    )
    svc = ResearchFactorComputationService((definition,), (TextCalculator(),))

    result = svc.compute_factor(
        vector(feature("net_margin", "1")),
        factor_key="quality_label",
        definition_version="1",
    )

    assert result.value_text == "strong"
    assert result.value_numeric is None
    assert result.unit is None
