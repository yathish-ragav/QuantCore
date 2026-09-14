from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_portfolio_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioFactorExposureResponse,
    ResearchPortfolioFactorRiskResponse,
    ResearchPortfolioRequest,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductService,
)
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition


router = APIRouter(
    prefix="/api/v1/research/portfolios/factor-risk",
    tags=["Research Portfolio Factor Risk"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_PORTFOLIO_FACTOR_RISK_ROWS = 1000


@router.post("", response_model=ResearchPortfolioFactorRiskResponse)
def assess_research_portfolio_factor_risk(
    request: ResearchPortfolioRequest,
    portfolio_product_service: ResearchPortfolioProductService = Depends(
        get_research_portfolio_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_PORTFOLIO_FACTOR_RISK_ROWS:
        raise InvalidInputError(
            "Research portfolio factor risk request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_FACTOR_RISK_ROWS} symbol/as-of rows."
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

    result = portfolio_product_service.construct_with_factor_risk(
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

    snapshot = result.factor_risk
    return ResearchPortfolioFactorRiskResponse(
        strategy_key=snapshot.strategy_key,
        strategy_definition_version=snapshot.strategy_definition_version,
        signal_identity=snapshot.signal_identity,
        as_of=snapshot.as_of,
        position_count=snapshot.position_count,
        factor_exposures=[
            ResearchPortfolioFactorExposureResponse(
                factor_identity=exposure.factor_identity,
                as_of=exposure.as_of,
                position_count=exposure.position_count,
                factor_observation_count=exposure.factor_observation_count,
                exposure=exposure.exposure,
                long_exposure=exposure.long_exposure,
                short_exposure=exposure.short_exposure,
                gross_factor_exposure=exposure.gross_factor_exposure,
                gross_normalized_exposure=exposure.gross_normalized_exposure,
            )
            for exposure in snapshot.factor_exposures
        ],
        dataset_fingerprint=result.portfolio.dataset_fingerprint,
        dataset_identity=result.portfolio.dataset_identity,
        signal_construction=result.portfolio.signal_construction,
    )
