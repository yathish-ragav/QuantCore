from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductResult,
    ResearchPortfolioProductService,
)
from quantcore.services.research_signal_service import (
    ResearchSignalDefinition,
    ResearchSignalPanel,
)
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
