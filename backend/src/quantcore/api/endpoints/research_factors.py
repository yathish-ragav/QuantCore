from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import (
    get_research_dataset_service,
    get_research_factor_computation_service,
)
from quantcore.schemas.research_factors import ResearchFactorValueResponse
from quantcore.services.research_dataset_service import ResearchDatasetService
from quantcore.services.research_factor_computation_service import (
    ResearchFactorComputationService,
)


router = APIRouter(
    prefix="/api/v1/research/factors",
    tags=["Research Factors"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)


@router.get(
    "/{symbol}",
    response_model=ResearchFactorValueResponse,
)
def get_research_factor(
    symbol: str,
    factor_key: str = Query(..., min_length=1, max_length=100),
    definition_version: str = Query(..., min_length=1, max_length=100),
    as_of: datetime = Query(
        ...,
        description=(
            "Knowledge-boundary timestamp. Only PIT feature observations known "
            "by this timestamp are used."
        ),
    ),
    dataset_service: ResearchDatasetService = Depends(
        get_research_dataset_service
    ),
    factor_service: ResearchFactorComputationService = Depends(
        get_research_factor_computation_service
    ),
):
    feature_vector = dataset_service.build_feature_vector(
        symbol,
        as_of=as_of,
    )
    factor = factor_service.compute_factor(
        feature_vector,
        factor_key=factor_key,
        definition_version=definition_version,
    )
    return ResearchFactorValueResponse(
        factor_key=factor.factor_key,
        definition_version=factor.definition_version,
        symbol=factor.symbol,
        security_id=factor.security_id,
        as_of=factor.as_of,
        value_numeric=factor.value_numeric,
        value_text=factor.value_text,
        unit=factor.unit,
        input_manifest=(
            dict(factor.input_manifest)
            if factor.input_manifest is not None
            else None
        ),
    )
