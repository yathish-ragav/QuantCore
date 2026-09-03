import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyDefinitionRegistry,
    ResearchStrategyDirection,
    ResearchStrategyService,
)


def definition(**overrides):
    values = {
        "strategy_key": "quality_long",
        "definition_version": "1",
        "signal_identity": ("quality_signal", "1"),
        "direction": ResearchStrategyDirection.LONG_ONLY,
        "long_threshold": 0.8,
    }
    values.update(overrides)
    return ResearchStrategyDefinition(**values)


def test_accepts_long_only_strategy_definition():
    result = definition()
    assert result.identity == ("quality_long", "1")
    assert result.signal_identity == ("quality_signal", "1")
    assert result.long_threshold == pytest.approx(0.8)
    assert result.short_threshold is None


def test_accepts_short_only_strategy_definition():
    result = definition(
        strategy_key="quality_short",
        direction=ResearchStrategyDirection.SHORT_ONLY,
        long_threshold=None,
        short_threshold=0.2,
    )
    assert result.direction is ResearchStrategyDirection.SHORT_ONLY
    assert result.short_threshold == pytest.approx(0.2)


def test_accepts_long_short_strategy_definition():
    result = definition(
        strategy_key="quality_long_short",
        direction=ResearchStrategyDirection.LONG_SHORT,
        long_threshold=0.8,
        short_threshold=0.2,
    )
    assert result.direction is ResearchStrategyDirection.LONG_SHORT


def test_coerces_valid_direction_string():
    result = definition(direction="LONG_ONLY")
    assert result.direction is ResearchStrategyDirection.LONG_ONLY


@pytest.mark.parametrize(
    "direction, kwargs",
    [
        (ResearchStrategyDirection.LONG_ONLY, {"short_threshold": 0.2}),
        (ResearchStrategyDirection.SHORT_ONLY, {"long_threshold": 0.8}),
        (ResearchStrategyDirection.LONG_SHORT, {"long_threshold": 0.8}),
        (ResearchStrategyDirection.LONG_SHORT, {"long_threshold": None, "short_threshold": 0.2}),
    ],
)
def test_rejects_missing_or_forbidden_thresholds(direction, kwargs):
    with pytest.raises(InvalidInputError):
        definition(direction=direction, **kwargs)


def test_rejects_overlapping_long_short_thresholds():
    with pytest.raises(InvalidInputError):
        definition(
            direction=ResearchStrategyDirection.LONG_SHORT,
            long_threshold=0.5,
            short_threshold=0.5,
        )


def test_rejects_threshold_outside_signal_score_range():
    with pytest.raises(InvalidInputError):
        definition(long_threshold=1.1)


def test_rejects_non_finite_threshold():
    with pytest.raises(InvalidInputError):
        definition(long_threshold=float("nan"))


def test_rejects_boolean_threshold():
    with pytest.raises(InvalidInputError):
        definition(long_threshold=True)


def test_rejects_invalid_signal_identity():
    with pytest.raises(InvalidInputError):
        definition(signal_identity=("", "1"))


def test_rejects_non_string_strategy_identity():
    with pytest.raises(InvalidInputError):
        definition(strategy_key=123)


def test_registry_preserves_registration_order_and_resolves_identity():
    first = definition(strategy_key="first")
    second = definition(strategy_key="second")
    registry = ResearchStrategyDefinitionRegistry((first, second))
    assert registry.definitions() == (first, second)
    assert registry.get("first", "1") is first
    assert registry.get("second", "1") is second


def test_registry_rejects_duplicate_identity():
    first = definition()
    with pytest.raises(InvalidInputError):
        ResearchStrategyDefinitionRegistry((first, first))


def test_registry_rejects_unknown_identity():
    registry = ResearchStrategyDefinitionRegistry((definition(),))
    with pytest.raises(ResourceNotFoundError):
        registry.get("missing", "1")


def test_validation_service_preserves_definition():
    result = definition()
    assert ResearchStrategyService.validate_definition(result) is result


def test_description_is_normalized():
    result = definition(description="  Quality strategy  ")
    assert result.description == "Quality strategy"
