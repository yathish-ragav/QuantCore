from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_product_service import (
    ResearchBacktestProductResult,
    ResearchBacktestProductService,
)
from quantcore.services.research_backtest_service import ResearchBacktestDefinition
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
)
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition, ResearchRebalanceFrequency
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition, ResearchStrategyDirection
from quantcore.services.research_transaction_cost_service import ResearchTransactionCostDefinition

AS_OF_0 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)


def signal():
    return ResearchSignalDefinition(
        signal_key="quality_signal",
        definition_version="1",
        factor_identities=(("quality", "1"),),
        weights=(1.0,),
    )


def strategy():
    return ResearchStrategyDefinition(
        strategy_key="quality_long",
        definition_version="1",
        signal_identity=("quality_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.8,
    )


def definitions():
    return (
        ResearchBacktestDefinition(
            backtest_key="quality_backtest",
            definition_version="1",
            strategy_identity=("quality_long", "1"),
            constraint_identity=("basic", "1"),
            rebalance_identity=("daily", "1"),
            transaction_cost_identity=("tc", "1"),
            start_as_of=AS_OF_0,
            end_as_of=AS_OF_1,
            initial_capital=1_000_000,
            price_basis=PriceBasis.UNADJUSTED,
        ),
        ResearchPortfolioConstraintDefinition(
            constraint_key="basic",
            definition_version="1",
            max_position_weight=1.0,
            max_gross_exposure=1.0,
        ),
        ResearchRebalanceDefinition(
            rebalance_key="daily",
            definition_version="1",
            frequency=ResearchRebalanceFrequency.DAILY,
        ),
        ResearchTransactionCostDefinition(
            cost_key="tc",
            definition_version="1",
            one_way_cost_bps=10.0,
        ),
    )


def portfolio_result(as_of, symbol="AAA", security_id=10):
    position = Mock(
        symbol=symbol,
        security_id=security_id,
        target_weight=1.0,
    )
    portfolio = Mock(
        positions=(position,),
        as_of=as_of,
    )
    return Mock(
        portfolio=portfolio,
        dataset_fingerprint=f"fp-{as_of.date().isoformat()}",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )


def test_run_constructs_targets_once_and_loads_all_pit_revisions():
    portfolio_product = Mock()
    first = portfolio_result(AS_OF_0)
    second = portfolio_result(AS_OF_1)
    portfolio_product.construct_sequence.return_value = (first, second)

    price_service = Mock()
    naive_date = datetime(2026, 8, 20, 16, 0)
    known_at = datetime(2026, 8, 20, 16, 30, tzinfo=timezone.utc)
    revision_1 = Mock(
        date=naive_date,
        close=100.0,
        adjusted_close=100.0,
        known_at=known_at,
        revision_number=1,
    )
    revision_2 = Mock(
        date=naive_date,
        close=110.0,
        adjusted_close=110.0,
        known_at=AS_OF_1,
        revision_number=2,
    )
    price_service.get_price_revision_history_known_as_of.return_value = [
        revision_1,
        revision_2,
    ]

    backtest_service = Mock()
    expected_backtest = Mock()
    backtest_service.run.return_value = expected_backtest

    service = ResearchBacktestProductService(
        portfolio_product,
        price_service,
        backtest_service,
    )
    backtest_definition, constraint, rebalance, cost = definitions()

    result = service.run(
        symbols=["AAA"],
        as_ofs=(AS_OF_0, AS_OF_1),
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
        backtest_definition=backtest_definition,
        constraint_definition=constraint,
        rebalance_definition=rebalance,
        transaction_cost_definition=cost,
    )

    assert isinstance(result, ResearchBacktestProductResult)
    assert result.backtest is expected_backtest
    assert result.target_portfolios == (first, second)
    portfolio_product.construct_sequence.assert_called_once()
    price_service.get_price_revision_history_known_as_of.assert_called_once_with(
        "AAA",
        AS_OF_1,
    )
    passed_history = backtest_service.run.call_args.args[2]
    assert 10 in passed_history
    assert passed_history[10][0].date.tzinfo is not None
    assert passed_history[10][0].date == naive_date.replace(tzinfo=timezone.utc)
    assert passed_history[10][0].known_at == known_at
    backtest_service.run.assert_called_once_with(
        backtest_definition,
        (first.portfolio, second.portfolio),
        passed_history,
        constraint,
        rebalance,
        cost,
    )


def test_run_rejects_non_backtest_definition():
    service = ResearchBacktestProductService(Mock(), Mock(), Mock())
    _, constraint, rebalance, cost = definitions()

    with pytest.raises(InvalidInputError, match="ResearchBacktestDefinition"):
        service.run(
            symbols=["AAA"],
            as_ofs=(AS_OF_0, AS_OF_1),
            definition_identities=None,
            dataset_identity=None,
            signal=signal(),
            factors=(("quality", "1", 1.0, True),),
            strategy=strategy(),
            backtest_definition=Mock(),
            constraint_definition=constraint,
            rebalance_definition=rebalance,
            transaction_cost_definition=cost,
        )


def test_run_reuses_one_price_history_query_per_security():
    portfolio_product = Mock()
    first = portfolio_result(AS_OF_0, "AAA", 10)
    second = portfolio_result(AS_OF_1, "BBB", 20)
    portfolio_product.construct_sequence.return_value = (first, second)

    price_service = Mock()
    price_service.get_price_revision_history_known_as_of.side_effect = [[], []]
    backtest_service = Mock()
    backtest_service.run.return_value = Mock()

    service = ResearchBacktestProductService(portfolio_product, price_service, backtest_service)
    backtest_definition, constraint, rebalance, cost = definitions()

    service.run(
        symbols=["AAA", "BBB"],
        as_ofs=(AS_OF_0, AS_OF_1),
        definition_identities=None,
        dataset_identity=None,
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
        backtest_definition=backtest_definition,
        constraint_definition=constraint,
        rebalance_definition=rebalance,
        transaction_cost_definition=cost,
    )

    assert price_service.get_price_revision_history_known_as_of.call_count == 2
    assert [
        call.args for call in price_service.get_price_revision_history_known_as_of.call_args_list
    ] == [("AAA", AS_OF_1), ("BBB", AS_OF_1)]


def test_run_rejects_conflicting_symbol_mapping_for_security():
    portfolio_product = Mock()
    first = portfolio_result(AS_OF_0, "AAA", 10)
    second = portfolio_result(AS_OF_1, "BBB", 10)
    portfolio_product.construct_sequence.return_value = (first, second)

    service = ResearchBacktestProductService(portfolio_product, Mock(), Mock())
    backtest_definition, constraint, rebalance, cost = definitions()

    with pytest.raises(InvalidInputError, match="conflicting symbols"):
        service.run(
            symbols=["AAA", "BBB"],
            as_ofs=(AS_OF_0, AS_OF_1),
            definition_identities=None,
            dataset_identity=None,
            signal=signal(),
            factors=(("quality", "1", 1.0, True),),
            strategy=strategy(),
            backtest_definition=backtest_definition,
            constraint_definition=constraint,
            rebalance_definition=rebalance,
            transaction_cost_definition=cost,
        )
