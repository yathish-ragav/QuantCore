from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_portfolio_product_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioStressImpactResponse,
    ResearchPortfolioStressRequest,
    ResearchPortfolioStressResponse,
)
from quantcore.services.research_portfolio_product_service import ResearchPortfolioProductService
from quantcore.services.research_portfolio_stress_service import ResearchStressScenarioDefinition
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition

router = APIRouter(
    prefix="/api/v1/research/portfolios/stress",
    tags=["Research Portfolio Stress"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_PORTFOLIO_STRESS_ROWS = 1000
MAX_RESEARCH_PORTFOLIO_STRESS_SHOCKS = 100


@router.post("", response_model=ResearchPortfolioStressResponse)
def assess_research_portfolio_stress(
    request: ResearchPortfolioStressRequest,
    portfolio_product_service: ResearchPortfolioProductService = Depends(
        get_research_portfolio_product_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_PORTFOLIO_STRESS_ROWS:
        raise InvalidInputError(
            "Research portfolio stress request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_STRESS_ROWS} symbol/as-of rows."
        )
    if len(request.shocks_by_security) > MAX_RESEARCH_PORTFOLIO_STRESS_SHOCKS:
        raise InvalidInputError(
            "Research portfolio stress request exceeds the maximum of "
            f"{MAX_RESEARCH_PORTFOLIO_STRESS_SHOCKS} explicit security shocks."
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
    scenario = ResearchStressScenarioDefinition(
        scenario_key=request.scenario_key,
        definition_version=request.scenario_definition_version,
        shocks_by_security=request.shocks_by_security,
        default_shock=request.default_shock,
        description=request.scenario_description,
    )

    result = portfolio_product_service.construct_with_stress(
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
        scenario=scenario,
        portfolio_value=request.portfolio_value,
    )

    stress = result.stress
    return ResearchPortfolioStressResponse(
        scenario_key=stress.scenario_identity[0],
        scenario_definition_version=stress.scenario_identity[1],
        strategy_key=stress.strategy_key,
        strategy_definition_version=stress.strategy_definition_version,
        signal_identity=stress.signal_identity,
        as_of=stress.as_of,
        position_count=stress.position_count,
        shocked_position_count=stress.shocked_position_count,
        portfolio_return=stress.portfolio_return,
        portfolio_value=stress.portfolio_value,
        pnl_amount=stress.pnl_amount,
        stressed_value=stress.stressed_value,
        best_position_contribution=stress.best_position_contribution,
        worst_position_contribution=stress.worst_position_contribution,
        dataset_fingerprint=result.portfolio.dataset_fingerprint,
        dataset_identity=result.portfolio.dataset_identity,
        signal_construction=result.portfolio.signal_construction,
        impacts=[
            ResearchPortfolioStressImpactResponse(
                security_id=impact.security_id,
                symbol=impact.symbol,
                target_weight=impact.target_weight,
                shock=impact.shock,
                contribution=impact.contribution,
            )
            for impact in stress.impacts
        ],
    )
