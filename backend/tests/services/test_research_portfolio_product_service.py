from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceDefinition,
    ResearchRebalanceFrequency,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductResult,
    ResearchPortfolioProductService,
    ResearchPortfolioRebalanceProductResult,
)
from quantcore.services.research_signal_service import (
    ResearchSignalDefinition,
    ResearchSignalPanel,
)
from quantcore.services.research_transaction_cost_service import ResearchTransactionCostDefinition
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyDirection,
)

AS_OF = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def strategy():
    return ResearchStrategyDefinition(
        strategy_key="quality_long",
        definition_version="1",
        signal_identity=("quality_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.8,
    )


def signal():
    return ResearchSignalDefinition(
        signal_key="quality_signal",
        definition_version="1",
        factor_identities=(("quality", "1"),),
        weights=(1.0,),
    )


def test_construct_composes_existing_deterministic_services():
    historical = Mock()
    dataset = Mock(
        dataset_fingerprint="dataset-fp",
        dataset_identity=("dataset", "1"),
    )
    historical.build_historical_dataset.return_value = dataset

    panel = Mock()
    panel.build_factor_panel.return_value = "raw-panel"

    cross_sectional = Mock()
    ranked = Mock()
    cross_sectional.rank_factor_panel.return_value = ranked

    signal_service = Mock()
    composite = Mock(
        signal_key="quality_signal",
        definition_version="1",
        construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )
    signal_service.construct_signal.return_value = composite

    strategy_service = Mock()
    strategy_service.validate_definition.return_value = strategy()

    portfolio_service = Mock()
    expected = ResearchPortfolio(
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF,
        status=ResearchPortfolioConstructionStatus.CONSTRUCTED,
        positions=(),
        eligible_count=0,
        long_count=0,
        short_count=0,
        gross_exposure=0.0,
        net_exposure=0.0,
        construction="EQUAL_WEIGHT_LONG_ONLY",
    )
    portfolio_service.construct.return_value = expected

    service = ResearchPortfolioProductService(
        historical,
        panel,
        cross_sectional,
        signal_service,
        strategy_service,
        portfolio_service,
    )

    result = service.construct(
        symbols=["AAA"],
        as_ofs=[AS_OF],
        target_as_of=AS_OF,
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
    )

    assert result.portfolio is expected
    assert result.dataset_fingerprint == "dataset-fp"
    assert result.dataset_identity == ("dataset", "1")
    assert result.signal_construction == "WEIGHTED_NORMALIZED_RANK_AVERAGE"

    historical.build_historical_dataset.assert_called_once()

    panel.build_factor_panel.assert_called_once_with(
        dataset,
        factor_key="quality",
        definition_version="1",
    )

    cross_sectional.rank_factor_panel.assert_called_once_with(
        "raw-panel",
        higher_is_better=True,
    )

    signal_service.construct_signal.assert_called_once()

    portfolio_service.construct.assert_called_once_with(
        strategy(),
        composite,
        AS_OF,
    )


def test_construct_rejects_target_as_of_outside_requested_signal_points():
    service = ResearchPortfolioProductService(
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )

    with pytest.raises(Exception, match="target_as_of"):
        service.construct(
            symbols=["AAA"],
            as_ofs=[AS_OF],
            target_as_of=datetime(
                2026,
                8,
                21,
                15,
                30,
                tzinfo=timezone.utc,
            ),
            definition_identities=None,
            dataset_identity=None,
            signal=signal(),
            factors=(("quality", "1", 1.0, True),),
            strategy=strategy(),
        )


def test_construct_with_risk_composes_existing_risk_service():
    portfolio_service = ResearchPortfolioProductService(
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )

    portfolio_result = ResearchPortfolioProductResult(
        portfolio=Mock(),
        dataset_fingerprint="dataset-fp",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )

    portfolio_service.construct = Mock(return_value=portfolio_result)

    risk_service = Mock()
    risk_snapshot = Mock(strategy_key="quality_long")
    risk_service.snapshot.return_value = risk_snapshot

    portfolio_service._risk_service = risk_service

    result = portfolio_service.construct_with_risk(
        symbols=["AAA"],
        as_ofs=[AS_OF],
        target_as_of=AS_OF,
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
    )

    assert result.portfolio is portfolio_result
    assert result.risk is risk_snapshot

    portfolio_service.construct.assert_called_once()

    risk_service.snapshot.assert_called_once_with(
        portfolio_result.portfolio,
    )


def test_construct_with_factor_risk_composes_existing_factor_risk_service():
    portfolio_service = ResearchPortfolioProductService(
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )

    portfolio_result = ResearchPortfolioProductResult(
        portfolio=Mock(),
        dataset_fingerprint="dataset-fp",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )

    ranked_panels = {
        ("quality", "1"): Mock(),
    }

    portfolio_service._construct_with_ranked_panels = Mock(
        return_value=(portfolio_result, ranked_panels),
    )

    factor_risk_service = Mock()
    factor_risk_snapshot = Mock(strategy_key="quality_long")
    factor_risk_service.snapshot.return_value = factor_risk_snapshot

    portfolio_service._factor_risk_service = factor_risk_service

    result = portfolio_service.construct_with_factor_risk(
        symbols=["AAA"],
        as_ofs=[AS_OF],
        target_as_of=AS_OF,
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
    )

    assert result.portfolio is portfolio_result
    assert result.factor_risk is factor_risk_snapshot

    portfolio_service._construct_with_ranked_panels.assert_called_once_with(
        symbols=["AAA"],
        as_ofs=[AS_OF],
        target_as_of=AS_OF,
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
    )

    factor_risk_service.snapshot.assert_called_once_with(
        portfolio_result.portfolio,
        ranked_panels,
    )


def test_construct_with_constraints_composes_existing_constraint_service():
    portfolio_service = ResearchPortfolioProductService(
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )
    portfolio_result = ResearchPortfolioProductResult(
        portfolio=Mock(),
        dataset_fingerprint="dataset-fp",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )
    portfolio_service.construct = Mock(return_value=portfolio_result)

    constraint_definition = Mock()
    constraint_result = Mock()
    constraint_service = Mock()
    constraint_service.validate.return_value = constraint_result
    portfolio_service._constraint_service = constraint_service

    result = portfolio_service.construct_with_constraints(
        symbols=["AAA"],
        as_ofs=[AS_OF],
        target_as_of=AS_OF,
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
        constraint_definition=constraint_definition,
    )

    assert result.portfolio is portfolio_result
    assert result.constraint is constraint_result
    portfolio_service.construct.assert_called_once()
    constraint_service.validate.assert_called_once_with(
        portfolio_result.portfolio,
        constraint_definition,
    )


def test_construct_with_rebalance_constructs_current_and_target_states():
    historical = Mock()
    dataset = Mock(
        dataset_fingerprint="dataset-fp",
        dataset_identity=("dataset", "1"),
    )
    historical.build_historical_dataset.return_value = dataset

    panel = Mock()
    panel.build_factor_panel.return_value = "raw-panel"
    cross_sectional = Mock()
    cross_sectional.rank_factor_panel.return_value = Mock()

    signal_service = Mock()
    composite = Mock(
        construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )
    signal_service.construct_signal.return_value = composite

    strategy_service = Mock()
    strategy_service.validate_definition.return_value = strategy()

    portfolio_service = Mock()
    current_portfolio = Mock(
        as_of=AS_OF,
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
    )
    target_as_of = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)
    target_portfolio = Mock(
        as_of=target_as_of,
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
    )
    portfolio_service.construct.side_effect = [
        current_portfolio,
        target_portfolio,
    ]

    rebalance_service = Mock()
    rebalance = Mock()
    rebalance_service.rebalance.return_value = rebalance

    service = ResearchPortfolioProductService(
        historical,
        panel,
        cross_sectional,
        signal_service,
        strategy_service,
        portfolio_service,
        rebalance_service=rebalance_service,
    )

    rebalance_definition = ResearchRebalanceDefinition(
        rebalance_key="monthly",
        definition_version="1",
        frequency=ResearchRebalanceFrequency.MONTHLY,
    )

    result = service.construct_with_rebalance(
        symbols=["AAA"],
        as_ofs=[AS_OF, target_as_of],
        current_as_of=AS_OF,
        target_as_of=target_as_of,
        definition_identities=None,
        dataset_identity=("dataset", "1"),
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
        rebalance_definition=rebalance_definition,
    )

    assert result.current.portfolio is current_portfolio
    assert result.target.portfolio is target_portfolio
    assert result.current.dataset_fingerprint == "dataset-fp"
    assert result.target.dataset_fingerprint == "dataset-fp"
    assert result.rebalance is rebalance

    assert historical.build_historical_dataset.call_count == 2
    assert panel.build_factor_panel.call_count == 2
    assert signal_service.construct_signal.call_count == 2
    assert portfolio_service.construct.call_count == 2
    portfolio_service.construct.assert_any_call(
        strategy(),
        composite,
        AS_OF,
    )
    portfolio_service.construct.assert_any_call(
        strategy(),
        composite,
        target_as_of,
    )
    rebalance_service.rebalance.assert_called_once_with(
        current_portfolio,
        target_portfolio,
        rebalance_definition,
        target_as_of,
    )


def test_construct_with_transaction_cost_composes_rebalance_and_cost_service():
    portfolio_service = ResearchPortfolioProductService(
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )

    rebalance_result = ResearchPortfolioRebalanceProductResult(
        current=Mock(),
        target=Mock(),
        rebalance=Mock(),
    )
    portfolio_service.construct_with_rebalance = Mock(return_value=rebalance_result)

    cost_service = Mock()
    cost_result = Mock()
    cost_service.calculate.return_value = cost_result
    portfolio_service._transaction_cost_service = cost_service

    transaction_cost_definition = Mock(spec=ResearchTransactionCostDefinition)
    result = portfolio_service.construct_with_transaction_cost(
        symbols=["AAA"],
        as_ofs=(AS_OF,),
        current_as_of=AS_OF,
        target_as_of=AS_OF,
        definition_identities=None,
        dataset_identity=None,
        signal=signal(),
        factors=(("quality", "1", 1.0, True),),
        strategy=strategy(),
        rebalance_definition=Mock(spec=ResearchRebalanceDefinition),
        transaction_cost_definition=transaction_cost_definition,
    )

    assert result.current is rebalance_result.current
    assert result.target is rebalance_result.target
    assert result.rebalance is rebalance_result.rebalance
    assert result.transaction_cost is cost_result
    portfolio_service.construct_with_rebalance.assert_called_once()
    cost_service.calculate.assert_called_once_with(
        rebalance_result.rebalance,
        transaction_cost_definition,
    )


def test_construct_with_transaction_cost_rejects_invalid_cost_definition():
    portfolio_service = ResearchPortfolioProductService(
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )

    with pytest.raises(InvalidInputError, match="ResearchTransactionCostDefinition"):
        portfolio_service.construct_with_transaction_cost(
            symbols=["AAA"],
            as_ofs=(AS_OF,),
            current_as_of=AS_OF,
            target_as_of=AS_OF,
            definition_identities=None,
            dataset_identity=None,
            signal=signal(),
            factors=(("quality", "1", 1.0, True),),
            strategy=strategy(),
            rebalance_definition=Mock(spec=ResearchRebalanceDefinition),
            transaction_cost_definition=Mock(),
        )
