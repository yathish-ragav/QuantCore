from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.core.exceptions import InvalidInputError
from quantcore.api.dependencies import (
    get_research_portfolio_product_service,
)
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioRequest,
    ResearchPortfolioResponse,
    ResearchPortfolioPositionResponse,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductService,
)
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition


router = APIRouter(
    prefix="/api/v1/research/portfolios",
    tags=["Research Portfolios"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_PORTFOLIO_ROWS = 1000


@router.post("", response_model=ResearchPortfolioResponse)
def construct_research_portfolio(
    request: ResearchPortfolioRequest,
    portfolio_product_service: ResearchPortfolioProductService = Depends(
        get_research_portfolio_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_PORTFOLIO_ROWS:
        raise InvalidInputError(
            "Research portfolio request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_ROWS} symbol/as-of rows."
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

    portfolio = portfolio_product_service.construct(
        symbols=request.symbols,
        as_ofs=request.as_ofs,
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
    )

    return ResearchPortfolioResponse(
        strategy_key=portfolio.portfolio.strategy_key,
        strategy_definition_version=portfolio.portfolio.strategy_definition_version,
        signal_identity=portfolio.portfolio.signal_identity,
        as_of=portfolio.portfolio.as_of,
        status=portfolio.portfolio.status.value,
        construction=portfolio.portfolio.construction,
        eligible_count=portfolio.portfolio.eligible_count,
        long_count=portfolio.portfolio.long_count,
        short_count=portfolio.portfolio.short_count,
        gross_exposure=portfolio.portfolio.gross_exposure,
        net_exposure=portfolio.portfolio.net_exposure,
        dataset_fingerprint=portfolio.dataset_fingerprint,
        dataset_identity=portfolio.dataset_identity,
        signal_construction=portfolio.signal_construction,
        positions=[
            ResearchPortfolioPositionResponse(
                symbol=position.symbol,
                security_id=position.security_id,
                as_of=position.as_of,
                signal_score=position.signal_score,
                side=position.side.value,
                target_weight=position.target_weight,
            )
            for position in portfolio.portfolio.positions
        ],
    )
