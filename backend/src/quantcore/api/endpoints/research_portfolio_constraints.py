from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_portfolio_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioConstraintRequest,
    ResearchPortfolioConstraintResponse,
    ResearchPortfolioConstraintViolationResponse,
)
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductService,
)
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition


router = APIRouter(
    prefix="/api/v1/research/portfolios/constraints",
    tags=["Research Portfolio Constraints"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_PORTFOLIO_CONSTRAINT_ROWS = 1000


@router.post("", response_model=ResearchPortfolioConstraintResponse)
def validate_research_portfolio_constraints(
    request: ResearchPortfolioConstraintRequest,
    portfolio_product_service: ResearchPortfolioProductService = Depends(
        get_research_portfolio_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_PORTFOLIO_CONSTRAINT_ROWS:
        raise InvalidInputError(
            "Research portfolio constraint request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_CONSTRAINT_ROWS} symbol/as-of rows."
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
    constraint = ResearchPortfolioConstraintDefinition(
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

    result = portfolio_product_service.construct_with_constraints(
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
        constraint_definition=constraint,
    )

    snapshot = result.constraint
    return ResearchPortfolioConstraintResponse(
        constraint_key=snapshot.constraint_key,
        constraint_definition_version=snapshot.constraint_definition_version,
        strategy_key=snapshot.strategy_key,
        strategy_definition_version=snapshot.strategy_definition_version,
        signal_identity=snapshot.signal_identity,
        as_of=snapshot.as_of,
        dataset_fingerprint=result.portfolio.dataset_fingerprint,
        dataset_identity=result.portfolio.dataset_identity,
        signal_construction=result.portfolio.signal_construction,
        status=snapshot.status.value,
        violations=[
            ResearchPortfolioConstraintViolationResponse(
                constraint=violation.constraint,
                observed_value=violation.observed_value,
                limit=violation.limit,
            )
            for violation in snapshot.violations
        ],
        observed_max_position_weight=snapshot.observed_max_position_weight,
        observed_gross_exposure=snapshot.observed_gross_exposure,
        observed_net_exposure=snapshot.observed_net_exposure,
        observed_long_exposure=snapshot.observed_long_exposure,
        observed_short_exposure=snapshot.observed_short_exposure,
    )
