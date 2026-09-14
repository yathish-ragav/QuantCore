from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_backtest_attribution_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_backtests import (
    ResearchBacktestAttributionPeriodResponse,
    ResearchBacktestAttributionPositionResponse,
    ResearchBacktestAttributionProvenanceResponse,
    ResearchBacktestAttributionResponse,
    ResearchBacktestRequest,
)
from quantcore.services.research_backtest_attribution_product_service import (
    ResearchBacktestAttributionProductService,
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
    prefix="/api/v1/research/backtests/attribution",
    tags=["Research Backtest Attribution"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_BACKTEST_ATTRIBUTION_ROWS = 1000


@router.post("", response_model=ResearchBacktestAttributionResponse)
def analyze_research_backtest_attribution(
    request: ResearchBacktestRequest,
    attribution_product_service: ResearchBacktestAttributionProductService = Depends(
        get_research_backtest_attribution_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_BACKTEST_ATTRIBUTION_ROWS:
        raise InvalidInputError(
            "Research backtest attribution request exceeds the maximum of "
            f"{MAX_RESEARCH_BACKTEST_ATTRIBUTION_ROWS} symbol/as-of rows."
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

    result = attribution_product_service.analyze(
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
    attribution = result.attribution
    return ResearchBacktestAttributionResponse(
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
        total_gross_return=attribution.total_gross_return,
        total_transaction_cost_drag=attribution.total_transaction_cost_drag,
        total_net_return=attribution.total_net_return,
        total_long_contribution=attribution.total_long_contribution,
        total_short_contribution=attribution.total_short_contribution,
        total_transaction_cost_return_contribution=attribution.total_transaction_cost_return_contribution,
        periods=[
            ResearchBacktestAttributionPeriodResponse(
                period_start=period.period_start,
                period_end=period.period_end,
                starting_equity=period.starting_equity,
                ending_equity=period.ending_equity,
                gross_return=period.gross_return,
                transaction_cost_drag=period.transaction_cost_drag,
                net_return=period.net_return,
                long_contribution=period.long_contribution,
                short_contribution=period.short_contribution,
                return_contribution=period.return_contribution,
                transaction_cost_return_contribution=period.transaction_cost_return_contribution,
                position_contributions=[
                    ResearchBacktestAttributionPositionResponse(
                        period_start=item.period_start,
                        period_end=item.period_end,
                        symbol=item.symbol,
                        security_id=item.security_id,
                        target_weight=item.target_weight,
                        security_return=item.security_return,
                        gross_contribution=item.gross_contribution,
                        return_contribution=item.return_contribution,
                    )
                    for item in period.position_contributions
                ],
            )
            for period in attribution.periods
        ],
        target_portfolios=[
            ResearchBacktestAttributionProvenanceResponse(
                as_of=portfolio.portfolio.as_of,
                dataset_fingerprint=portfolio.dataset_fingerprint,
                dataset_identity=portfolio.dataset_identity,
            )
            for portfolio in result.backtest.target_portfolios
        ],
    )
