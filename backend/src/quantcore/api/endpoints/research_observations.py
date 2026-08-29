from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_research_observation_service
from quantcore.schemas.responses import ResearchObservationResponse
from quantcore.services.research_observation_service import ResearchObservationService


router = APIRouter(
    prefix="/research-observations",
    tags=["Research Observations"],
)


def _to_response(observation, symbol: str) -> ResearchObservationResponse:
    return ResearchObservationResponse(
        symbol=symbol,
        observation_key=observation.observation_key,
        definition_version=observation.definition_version,
        as_of=observation.as_of,
        value_numeric=observation.value_numeric,
        value_text=observation.value_text,
        unit=observation.unit,
        input_manifest=observation.input_manifest,
        input_fingerprint=observation.input_fingerprint,
        created_at=observation.created_at,
    )


@router.get(
    "/{symbol}",
    response_model=list[ResearchObservationResponse],
)
def get_research_observations(
    symbol: str,
    as_of: datetime = Query(
        ...,
        description="Knowledge-boundary timestamp. Only observations stored at this exact timestamp are returned.",
    ),
    service: ResearchObservationService = Depends(get_research_observation_service),
):
    normalized_symbol = symbol.strip().upper()
    observations = service.get_for_symbol_as_of(
        normalized_symbol,
        as_of=as_of,
    )
    return [
        _to_response(observation, normalized_symbol)
        for observation in observations
    ]


@router.get(
    "/{symbol}/latest",
    response_model=list[ResearchObservationResponse],
)
def get_latest_research_observations(
    symbol: str,
    as_of: datetime = Query(
        ...,
        description="Knowledge-boundary timestamp. Returns the latest stored observation for each definition known by this timestamp.",
    ),
    service: ResearchObservationService = Depends(get_research_observation_service),
):
    normalized_symbol = symbol.strip().upper()
    observations = service.get_latest_for_symbol_as_of(
        normalized_symbol,
        as_of=as_of,
    )
    return [
        _to_response(observation, normalized_symbol)
        for observation in observations
    ]
