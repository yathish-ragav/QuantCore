from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_strategy_service
from quantcore.schemas.research_strategies import (
    ResearchStrategyRequest,
    ResearchStrategyResponse,
)
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyService,
)


router = APIRouter(
    prefix="/api/v1/research/strategies",
    tags=["Research Strategies"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)


@router.post(
    "",
    response_model=ResearchStrategyResponse,
)
def validate_research_strategy(
    request: ResearchStrategyRequest,
    strategy_service: ResearchStrategyService = Depends(get_research_strategy_service),
):
    definition = ResearchStrategyDefinition(
        strategy_key=request.strategy_key,
        definition_version=request.definition_version,
        signal_identity=request.signal_identity,
        direction=request.direction,
        long_threshold=request.long_threshold,
        short_threshold=request.short_threshold,
        description=request.description,
    )
    validated = strategy_service.validate_definition(definition)

    return ResearchStrategyResponse(
        strategy_key=validated.strategy_key,
        definition_version=validated.definition_version,
        signal_identity=validated.signal_identity,
        direction=validated.direction,
        long_threshold=validated.long_threshold,
        short_threshold=validated.short_threshold,
        description=validated.description,
    )
