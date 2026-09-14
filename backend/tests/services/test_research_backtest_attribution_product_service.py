from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_attribution_product_service import (
    ResearchBacktestAttributionProductResult,
    ResearchBacktestAttributionProductService,
)
from quantcore.services.research_backtest_service import ResearchBacktestDefinition


AS_OF_0 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)


def test_analyze_reuses_backtest_price_history_for_attribution():
    backtest_product = Mock()
    backtest_result = Mock()
    backtest = Mock()
    backtest_result.backtest = backtest
    backtest_result.target_portfolios = (Mock(),)
    backtest_result.target_portfolios[0].portfolio = Mock()
    backtest_result.price_history_by_security = {1: ("price",)}
    backtest_product.run.return_value = backtest_result

    attribution_service = Mock()
    attribution = Mock()
    attribution_service.attribute.return_value = attribution
    service = ResearchBacktestAttributionProductService(
        backtest_product, attribution_service
    )

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

    assert isinstance(result, ResearchBacktestAttributionProductResult)
    assert result.backtest is backtest_result
    assert result.attribution is attribution
    attribution_service.attribute.assert_called_once_with(
        backtest,
        (backtest_result.target_portfolios[0].portfolio,),
        {1: ("price",)},
    )


def test_analyze_rejects_missing_price_history():
    backtest_product = Mock()
    backtest_result = Mock()
    backtest_result.price_history_by_security = None
    backtest_product.run.return_value = backtest_result
    service = ResearchBacktestAttributionProductService(backtest_product, Mock())

    with pytest.raises(InvalidInputError, match="valuation price history"):
        service.analyze(
            symbols=["AAA"],
            as_ofs=(AS_OF_0, AS_OF_1),
            definition_identities=None,
            dataset_identity=None,
            signal=Mock(),
            factors=(("quality", "1", 1.0, True),),
            strategy=Mock(),
            backtest_definition=Mock(spec=ResearchBacktestDefinition),
            constraint_definition=Mock(),
            rebalance_definition=Mock(),
            transaction_cost_definition=Mock(),
        )


def test_analyze_rejects_non_backtest_definition():
    service = ResearchBacktestAttributionProductService(Mock(), Mock())
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
