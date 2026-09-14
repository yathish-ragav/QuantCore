from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_portfolio_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioTransactionCostRequest,
    ResearchPortfolioTransactionCostResponse,
)
from quantcore.services.research_portfolio_product_service import ResearchPortfolioProductService
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition
from quantcore.services.research_transaction_cost_service import ResearchTransactionCostDefinition

router = APIRouter(
    prefix="/api/v1/research/portfolios/transaction-costs",
    tags=["Research Portfolio Transaction Costs"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_PORTFOLIO_TRANSACTION_COST_ROWS = 1000


@router.post("", response_model=ResearchPortfolioTransactionCostResponse)
def calculate_research_portfolio_transaction_cost(
    request: ResearchPortfolioTransactionCostRequest,
    portfolio_product_service: ResearchPortfolioProductService = Depends(
        get_research_portfolio_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_PORTFOLIO_TRANSACTION_COST_ROWS:
        raise InvalidInputError(
            "Research portfolio transaction-cost request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_TRANSACTION_COST_ROWS} symbol/as-of rows."
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

    result = portfolio_product_service.construct_with_transaction_cost(
        symbols=request.symbols,
        as_ofs=request.as_ofs,
        current_as_of=request.current_as_of,
        target_as_of=request.target_as_of,
        definition_identities=request.definition_identities,
        dataset_identity=request.dataset_identity,
        signal=signal,
        factors=tuple(
            (
                factor.factor_key,
                factor.definition_version,
                factor.weight,
                factor.higher_is_better,
            )
            for factor in request.factors
        ),
        strategy=strategy,
        rebalance_definition=rebalance_definition,
        transaction_cost_definition=transaction_cost_definition,
    )

    cost = result.transaction_cost
    return ResearchPortfolioTransactionCostResponse(
        cost_key=cost.cost_key,
        cost_definition_version=cost.cost_definition_version,
        rebalance_key=cost.rebalance_key,
        rebalance_definition_version=cost.rebalance_definition_version,
        strategy_key=cost.strategy_key,
        strategy_definition_version=cost.strategy_definition_version,
        signal_identity=cost.signal_identity,
        frequency=result.rebalance.frequency,
        current_as_of=result.rebalance.current_as_of,
        as_of=cost.as_of,
        current_dataset_fingerprint=result.current.dataset_fingerprint,
        current_dataset_identity=result.current.dataset_identity,
        target_dataset_fingerprint=result.target.dataset_fingerprint,
        target_dataset_identity=result.target.dataset_identity,
        signal_construction=result.target.signal_construction,
        turnover=cost.turnover,
        one_way_cost_bps=cost.one_way_cost_bps,
        cost_fraction=cost.cost_fraction,
        cost_bps=cost.cost_bps,
        status=cost.status.value,
    )
