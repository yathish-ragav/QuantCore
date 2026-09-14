from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_performance_product_service import (
    ResearchBacktestPerformanceProductResult,
    ResearchBacktestPerformanceProductService,
)
from quantcore.services.research_backtest_service import ResearchBacktestDefinition


AS_OF_0 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)


def test_analyze_delegates_to_backtest_and_performance_services():
    backtest_product = Mock()
    backtest_result = Mock()
    backtest = Mock()
    backtest_result.backtest = backtest
    backtest_product.run.return_value = backtest_result

    performance_service = Mock()
    performance = Mock()
    performance_service.analyze.return_value = performance
    service = ResearchBacktestPerformanceProductService(backtest_product, performance_service)

    definition = Mock(spec=ResearchBacktestDefinition)
    result = service.analyze(
        symbols=["AAA"],
        as_ofs=(AS_OF_0, AS_OF_1),
        definition_identities=None,
        dataset_identity=None,
        signal=Mock(),
        factors=(("quality", "1", 1.0, True),),
        strategy=Mock(),
        backtest_definition=definition,
        constraint_definition=Mock(),
        rebalance_definition=Mock(),
        transaction_cost_definition=Mock(),
    )

    assert isinstance(result, ResearchBacktestPerformanceProductResult)
    assert result.backtest is backtest_result
    assert result.performance is performance
    backtest_product.run.assert_called_once()
    performance_service.analyze.assert_called_once_with(backtest)


def test_analyze_rejects_non_backtest_definition():
    service = ResearchBacktestPerformanceProductService(Mock(), Mock())
    with pytest.raises(InvalidInputError, match="ResearchBacktestDefinition"):
        service.analyze(
            symbols=["AAA"],
            as_ofs=(AS_OF_0, AS_OF_1),
            definition_identities=None,
            dataset_identity=None,
            signal=Mock(),
            factors=(("quality", "1", 1.0, True),),
            strategy=Mock(),
            backtest_definition=Mock(),
            constraint_definition=Mock(),
            rebalance_definition=Mock(),
            transaction_cost_definition=Mock(),
        )
