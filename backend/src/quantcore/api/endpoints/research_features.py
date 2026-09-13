from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_dataset_service
from quantcore.schemas.responses import (
    ResearchFeatureResponse,
    ResearchFeatureVectorResponse,
)
from quantcore.services.research_dataset_service import ResearchDatasetService


router = APIRouter(
    prefix="/api/v1/research/features",
    tags=["Research Features"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)


def _to_response(vector) -> ResearchFeatureVectorResponse:
    return ResearchFeatureVectorResponse(
        symbol=vector.symbol,
        security_id=vector.security_id,
        as_of=vector.as_of,
        input_fingerprint=vector.input_fingerprint,
        features=[
            ResearchFeatureResponse(
                observation_key=feature.observation_key,
                definition_version=feature.definition_version,
                observation_as_of=feature.observation_as_of,
                value_numeric=feature.value_numeric,
                value_text=feature.value_text,
                unit=feature.unit,
                input_manifest=feature.input_manifest,
                input_fingerprint=feature.input_fingerprint,
            )
            for feature in vector.features
        ],
    )


@router.get(
    "/{symbol}",
    response_model=ResearchFeatureVectorResponse,
)
def get_research_feature_vector(
    symbol: str,
    as_of: datetime = Query(
        ...,
        description="Knowledge-boundary timestamp. Only observations known by this timestamp are selected.",
    ),
    service: ResearchDatasetService = Depends(get_research_dataset_service),
):
    vector = service.build_feature_vector(
        symbol,
        as_of=as_of,
    )
    return _to_response(vector)
