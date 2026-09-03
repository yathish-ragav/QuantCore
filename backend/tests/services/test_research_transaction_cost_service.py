from dataclasses import replace
from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_rebalance_service import (
    ResearchRebalance,
    ResearchRebalanceAction,
    ResearchRebalanceActionType,
    ResearchRebalanceDefinition,
    ResearchRebalanceFrequency,
    ResearchRebalanceStatus,
)
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
    ResearchTransactionCostService,
    ResearchTransactionCostStatus,
)


AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def rebalance(turnover=0.4, status=ResearchRebalanceStatus.REBALANCED):
    action = ResearchRebalanceAction(
        symbol="TEST",
        security_id=1,
        current_weight=0.2,
        target_weight=0.1,
        weight_delta=-0.1,
        action=ResearchRebalanceActionType.REDUCE,
    )
    return ResearchRebalance(
        rebalance_key="weekly_quality",
        rebalance_definition_version="1",
        strategy_key="quality",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        frequency=ResearchRebalanceFrequency.WEEKLY,
        current_as_of=datetime(2025, 12, 26, 15, 30, tzinfo=timezone.utc),
        as_of=AS_OF,
        actions=(action,) if turnover else (),
        current_gross_exposure=1.0,
        current_net_exposure=1.0,
        target_gross_exposure=1.0,
        target_net_exposure=1.0,
        turnover=turnover,
        status=status,
    )


def definition(cost_bps=10.0):
    return ResearchTransactionCostDefinition("proportional", "1", cost_bps)


def test_definition_normalizes_identity_and_cost():
    result = ResearchTransactionCostDefinition(" cost ", " 1 ", 10)
    assert result.identity == ("cost", "1")
    assert result.one_way_cost_bps == 10.0


def test_definition_allows_zero_cost():
    assert definition(0).one_way_cost_bps == 0.0


@pytest.mark.parametrize("field,value", [("cost_key", ""), ("definition_version", "")])
def test_definition_rejects_empty_identity(field, value):
    values = {"cost_key": "cost", "definition_version": "1", "one_way_cost_bps": 10}
    values[field] = value
    with pytest.raises(InvalidInputError):
        ResearchTransactionCostDefinition(**values)


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True, "not-a-number"])
def test_definition_rejects_invalid_cost_bps(value):
    with pytest.raises(InvalidInputError):
        ResearchTransactionCostDefinition("cost", "1", value)


def test_calculates_proportional_cost_in_fraction_and_bps():
    result = ResearchTransactionCostService().calculate(rebalance(0.4), definition(10))
    assert result.turnover == pytest.approx(0.4)
    assert result.cost_bps == pytest.approx(4.0)
    assert result.cost_fraction == pytest.approx(0.0004)
    assert result.status is ResearchTransactionCostStatus.CALCULATED


def test_zero_turnover_has_zero_cost_and_explicit_status():
    result = ResearchTransactionCostService().calculate(rebalance(0.0), definition(25))
    assert result.cost_bps == 0.0
    assert result.cost_fraction == 0.0
    assert result.status is ResearchTransactionCostStatus.NO_TURNOVER


def test_result_preserves_rebalance_and_strategy_provenance():
    result = ResearchTransactionCostService().calculate(rebalance(0.25), definition(20))
    assert result.rebalance_key == "weekly_quality"
    assert result.rebalance_definition_version == "1"
    assert result.strategy_key == "quality"
    assert result.strategy_definition_version == "1"
    assert result.signal_identity == ("quality_signal", "1")
    assert result.as_of == AS_OF


def test_definition_identity_is_versioned():
    first = definition(10)
    second = definition(20)
    assert first.identity == second.identity
    assert first.one_way_cost_bps != second.one_way_cost_bps


def test_rejects_wrong_rebalance_type():
    with pytest.raises(InvalidInputError, match="ResearchRebalance"):
        ResearchTransactionCostService().calculate(object(), definition())


def test_rejects_wrong_definition_type():
    with pytest.raises(InvalidInputError, match="ResearchTransactionCostDefinition"):
        ResearchTransactionCostService().calculate(rebalance(), object())


def test_rejects_naive_rebalance_as_of():
    invalid = replace(rebalance(), as_of=AS_OF.replace(tzinfo=None))
    with pytest.raises(InvalidInputError, match="timezone-aware"):
        ResearchTransactionCostService().calculate(invalid, definition())


def test_rejects_negative_turnover():
    invalid = replace(rebalance(), turnover=-0.1)
    with pytest.raises(InvalidInputError, match="non-negative"):
        ResearchTransactionCostService().calculate(invalid, definition())


def test_rejects_non_finite_turnover():
    for value in (float("inf"), float("nan")):
        invalid = replace(rebalance(), turnover=value)
        with pytest.raises(InvalidInputError, match="finite"):
            ResearchTransactionCostService().calculate(invalid, definition())


def test_rejects_invalid_rebalance_status():
    invalid = replace(rebalance(), status="INVALID")
    with pytest.raises(InvalidInputError, match="valid rebalance status"):
        ResearchTransactionCostService().calculate(invalid, definition())


def test_calculation_is_deterministic():
    service = ResearchTransactionCostService()
    first = service.calculate(rebalance(0.1234), definition(17.5))
    second = service.calculate(rebalance(0.1234), definition(17.5))
    assert first == second


def test_cost_scales_linearly_with_turnover():
    service = ResearchTransactionCostService()
    low = service.calculate(rebalance(0.1), definition(10))
    high = service.calculate(rebalance(0.3), definition(10))
    assert high.cost_bps == pytest.approx(3 * low.cost_bps)
