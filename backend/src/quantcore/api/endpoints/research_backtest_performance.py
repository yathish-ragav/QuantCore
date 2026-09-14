from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_backtest_performance_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_backtests import (
    ResearchBacktestPerformanceProvenanceResponse,
    ResearchBacktestRequest,
    ResearchBacktestPerformanceResponse,
)
from quantcore.services.research_backtest_performance_product_service import (
    ResearchBacktestPerformanceProductService,
)
from quantcore.services.research_backtest_service import ResearchBacktestDefinition
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
)
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
)


router = APIRouter(
    prefix="/api/v1/research/backtests/performance",
    tags=["Research Backtest Performance"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_BACKTEST_PERFORMANCE_ROWS = 1000


@router.post("", response_model=ResearchBacktestPerformanceResponse)
def analyze_research_backtest_performance(
    request: ResearchBacktestRequest,
    performance_product_service: ResearchBacktestPerformanceProductService = Depends(
        get_research_backtest_performance_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_BACKTEST_PERFORMANCE_ROWS:
        raise InvalidInputError(
            "Research backtest performance request exceeds the maximum of "
            f"{MAX_RESEARCH_BACKTEST_PERFORMANCE_ROWS} symbol/as-of rows."
        )

    signal = ResearchSignalDefinition(
        signal_key=request.signal_key,
        definition_version=request.signal_definition_version,
        factor_identities=tuple(
            (factor.factor_key, factor.definition_version) for factor in request.factors
        ),
        weights=tuple(factor.weight for factor in request.factors),
        description=request.signal_description,
    )
    strategy = ResearchStrategyDefinition(
        strategy_key=request.strategy.strategy_key,
        definition_version=request.strategy.definition_version,
        signal_identity=request.strategy.signal_identity,
        direction=request.strategy.direction,
        long_threshold=request.strategy.long_threshold,
        short_threshold=request.strategy.short_threshold,
        description=request.strategy.description,
    )
    backtest_definition = ResearchBacktestDefinition(
        backtest_key=request.backtest_key,
        definition_version=request.backtest_definition_version,
        strategy_identity=(request.strategy.strategy_key, request.strategy.definition_version),
        constraint_identity=(request.constraint_key, request.constraint_definition_version),
        rebalance_identity=(request.rebalance_key, request.rebalance_definition_version),
        transaction_cost_identity=(request.cost_key, request.cost_definition_version),
        start_as_of=request.as_ofs[0],
        end_as_of=request.as_ofs[-1],
        initial_capital=request.initial_capital,
        price_basis=request.price_basis,
        description=request.backtest_description,
    )
    constraint_definition = ResearchPortfolioConstraintDefinition(
        constraint_key=request.constraint_key,
        definition_version=request.constraint_definition_version,
        max_position_weight=request.max_position_weight,
        max_gross_exposure=request.max_gross_exposure,
        min_net_exposure=request.min_net_exposure,
        max_net_exposure=request.max_net_exposure,
        max_long_exposure=request.max_long_exposure,
        max_short_exposure=request.max_short_exposure,
        description=request.constraint_description,
    )
    rebalance_definition = ResearchRebalanceDefinition(
        rebalance_key=request.rebalance_key,
        definition_version=request.rebalance_definition_version,
        frequency=request.frequency,
        description=request.rebalance_description,
    )
    transaction_cost_definition = ResearchTransactionCostDefinition(
        cost_key=request.cost_key,
        definition_version=request.cost_definition_version,
        one_way_cost_bps=request.one_way_cost_bps,
        description=request.cost_description,
    )

    result = performance_product_service.analyze(
        symbols=request.symbols,
        as_ofs=request.as_ofs,
        definition_identities=request.definition_identities,
        dataset_identity=request.dataset_identity,
        signal=signal,
        factors=tuple(
            (factor.factor_key, factor.definition_version, factor.weight, factor.higher_is_better)
            for factor in request.factors
        ),
        strategy=strategy,
        backtest_definition=backtest_definition,
        constraint_definition=constraint_definition,
        rebalance_definition=rebalance_definition,
        transaction_cost_definition=transaction_cost_definition,
    )
    backtest = result.backtest.backtest
    performance = result.performance
    return ResearchBacktestPerformanceResponse(
        backtest_key=backtest.backtest_key,
        backtest_definition_version=backtest.backtest_definition_version,
        strategy_identity=backtest.strategy_identity,
        constraint_identity=backtest.constraint_identity,
        rebalance_identity=backtest.rebalance_identity,
        transaction_cost_identity=backtest.transaction_cost_identity,
        start_as_of=backtest.start_as_of,
        end_as_of=backtest.end_as_of,
        initial_capital=backtest.initial_capital,
        final_equity=backtest.final_equity,
        total_return=backtest.total_return,
        price_basis=backtest.price_basis,
        period_count=performance.period_count,
        annualized_return=performance.annualized_return,
        annualized_volatility=performance.annualized_volatility,
        maximum_drawdown=performance.maximum_drawdown,
        maximum_drawdown_duration_days=performance.maximum_drawdown_duration_days,
        average_period_return=performance.average_period_return,
        winning_periods=performance.winning_periods,
        losing_periods=performance.losing_periods,
        flat_periods=performance.flat_periods,
        win_rate=performance.win_rate,
        average_turnover=performance.average_turnover,
        target_portfolios=[
            ResearchBacktestPerformanceProvenanceResponse(
                as_of=portfolio.portfolio.as_of,
                dataset_fingerprint=portfolio.dataset_fingerprint,
                dataset_identity=portfolio.dataset_identity,
            )
            for portfolio in result.backtest.target_portfolios
        ],
    )
