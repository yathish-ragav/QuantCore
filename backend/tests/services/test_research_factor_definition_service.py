import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_factor_definition_service import (
    ResearchFactorDefinition,
    ResearchFactorDefinitionRegistry,
)


def make_definition(**overrides):
    values = {
        "factor_key": "quality_score",
        "definition_version": "1",
        "required_feature_identities": (
            ("net_margin", "1"),
            ("operating_margin", "1"),
        ),
        "output_kind": "numeric",
        "unit": "score",
        "description": "Quality factor.",
    }
    values.update(overrides)
    return ResearchFactorDefinition(**values)


def test_factor_definition_normalizes_identity_and_feature_versions():
    definition = make_definition(
        factor_key=" quality_score ",
        definition_version=" 1 ",
        required_feature_identities=(
            (" net_margin ", " 1 "),
            (" operating_margin ", " 1 "),
        ),
        output_kind=" NUMERIC ",
        unit=" score ",
        description=" Quality factor. ",
    )

    assert definition.identity == ("quality_score", "1")
    assert definition.required_feature_identities == (
        ("net_margin", "1"),
        ("operating_margin", "1"),
    )
    assert definition.output_kind == "numeric"
    assert definition.unit == "score"
    assert definition.description == "Quality factor."


def test_factor_definition_rejects_empty_required_features():
    with pytest.raises(InvalidInputError):
        make_definition(required_feature_identities=())


def test_factor_definition_rejects_duplicate_required_feature_identity():
    with pytest.raises(InvalidInputError):
        make_definition(
            required_feature_identities=(
                ("net_margin", "1"),
                ("net_margin", "1"),
            )
        )


def test_factor_definition_rejects_invalid_output_kind():
    with pytest.raises(InvalidInputError):
        make_definition(output_kind="ratio")


def test_text_factor_rejects_unit():
    with pytest.raises(InvalidInputError):
        make_definition(output_kind="text", unit="score")


def test_registry_resolves_versioned_factor_definition():
    definition = make_definition()
    registry = ResearchFactorDefinitionRegistry((definition,))

    assert registry.get(" quality_score ", " 1 ") is definition
    assert registry.definitions() == (definition,)


def test_registry_rejects_duplicate_factor_identity():
    definition = make_definition()
    with pytest.raises(InvalidInputError):
        ResearchFactorDefinitionRegistry((definition, make_definition()))


def test_registry_rejects_unknown_factor_identity():
    registry = ResearchFactorDefinitionRegistry((make_definition(),))

    with pytest.raises(ResourceNotFoundError):
        registry.get("unknown_factor", "1")
