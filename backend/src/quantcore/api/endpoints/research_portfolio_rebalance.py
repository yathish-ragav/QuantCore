from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_portfolio_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioRebalanceActionResponse,
    ResearchPortfolioRebalanceRequest,
    ResearchPortfolioRebalanceResponse,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductService,
)
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition


router = APIRouter(
    prefix="/api/v1/research/portfolios/rebalance",
    tags=["Research Portfolio Rebalance"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_PORTFOLIO_REBALANCE_ROWS = 1000


@router.post("", response_model=ResearchPortfolioRebalanceResponse)
def rebalance_research_portfolio(
    request: ResearchPortfolioRebalanceRequest,
    portfolio_product_service: ResearchPortfolioProductService = Depends(
        get_research_portfolio_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_PORTFOLIO_REBALANCE_ROWS:
        raise InvalidInputError(
            "Research portfolio rebalance request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_REBALANCE_ROWS} symbol/as-of rows."
        )

    signal = ResearchSignalDefinition(
        signal_key=request.signal_key,
        definition_version=request.signal_definition_version,
        factor_identities=tuple(
            (factor.factor_key, factor.definition_version)
            for factor in request.factors
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
    definition = ResearchRebalanceDefinition(
        rebalance_key=request.rebalance_key,
        definition_version=request.rebalance_definition_version,
        frequency=request.frequency,
        description=request.rebalance_description,
    )

    result = portfolio_product_service.construct_with_rebalance(
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
        rebalance_definition=definition,
    )

    rebalance = result.rebalance
    return ResearchPortfolioRebalanceResponse(
        rebalance_key=rebalance.rebalance_key,
        rebalance_definition_version=rebalance.rebalance_definition_version,
        strategy_key=rebalance.strategy_key,
        strategy_definition_version=rebalance.strategy_definition_version,
        signal_identity=rebalance.signal_identity,
        frequency=rebalance.frequency,
        current_as_of=rebalance.current_as_of,
        as_of=rebalance.as_of,
        current_dataset_fingerprint=result.current.dataset_fingerprint,
        current_dataset_identity=result.current.dataset_identity,
        target_dataset_fingerprint=result.target.dataset_fingerprint,
        target_dataset_identity=result.target.dataset_identity,
        signal_construction=result.target.signal_construction,
        current_gross_exposure=rebalance.current_gross_exposure,
        current_net_exposure=rebalance.current_net_exposure,
        target_gross_exposure=rebalance.target_gross_exposure,
        target_net_exposure=rebalance.target_net_exposure,
        turnover=rebalance.turnover,
        status=rebalance.status.value,
        actions=[
            ResearchPortfolioRebalanceActionResponse(
                symbol=action.symbol,
                security_id=action.security_id,
                current_weight=action.current_weight,
                target_weight=action.target_weight,
                weight_delta=action.weight_delta,
                action=action.action,
            )
            for action in rebalance.actions
        ],
    )
