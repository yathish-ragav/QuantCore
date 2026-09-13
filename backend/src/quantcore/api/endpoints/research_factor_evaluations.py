from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import (
    get_research_factor_cross_sectional_service,
    get_research_factor_evaluation_service,
    get_research_factor_panel_service,
    get_research_historical_analysis_service,
)
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_factor_evaluations import (
    ResearchFactorEvaluationRequest,
    ResearchFactorEvaluationResponse,
    ResearchFactorEvaluationSliceResponse,
)
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_factor_evaluation_service import (
    ResearchFactorEvaluationService,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)


router = APIRouter(
    prefix="/api/v1/research/factors",
    tags=["Research Factor Evaluations"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_FACTOR_EVALUATION_ROWS = 1000


@router.post(
    "/evaluation",
    response_model=ResearchFactorEvaluationResponse,
)
def evaluate_research_factor(
    request: ResearchFactorEvaluationRequest,
    historical_service: ResearchHistoricalAnalysisService = Depends(
        get_research_historical_analysis_service
    ),
    panel_service: ResearchFactorPanelService = Depends(
        get_research_factor_panel_service
    ),
    cross_sectional_service: ResearchFactorCrossSectionalService = Depends(
        get_research_factor_cross_sectional_service
    ),
    evaluation_service: ResearchFactorEvaluationService = Depends(
        get_research_factor_evaluation_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_FACTOR_EVALUATION_ROWS:
        raise InvalidInputError(
            "Research factor evaluation request exceeds the maximum of "
            f"{MAX_FACTOR_EVALUATION_ROWS} symbol/as-of rows."
        )

    dataset = historical_service.build_historical_dataset(
        request.symbols,
        as_ofs=request.as_ofs,
        definition_identities=request.definition_identities,
        dataset_identity=request.dataset_identity,
    )
    panel = panel_service.build_factor_panel(
        dataset,
        factor_key=request.factor_key,
        definition_version=request.factor_definition_version,
    )
    ranked_panel = cross_sectional_service.rank_factor_panel(
        panel,
        higher_is_better=request.higher_is_better,
    )
    evaluation = evaluation_service.evaluate_ranked_panel(ranked_panel)

    return ResearchFactorEvaluationResponse(
        factor_key=evaluation.factor_key,
        definition_version=evaluation.definition_version,
        dataset_fingerprint=dataset.dataset_fingerprint,
        dataset_identity=dataset.dataset_identity,
        cross_section_count=evaluation.cross_section_count,
        total_observation_count=evaluation.total_observation_count,
        minimum_cross_section_size=evaluation.minimum_cross_section_size,
        maximum_cross_section_size=evaluation.maximum_cross_section_size,
        mean_cross_section_size=evaluation.mean_cross_section_size,
        mean_cross_section_value=evaluation.mean_cross_section_value,
        mean_cross_section_stddev=evaluation.mean_cross_section_stddev,
        mean_cross_section_range=evaluation.mean_cross_section_range,
        row_count=len(evaluation.cross_sections),
        cross_sections=[
            ResearchFactorEvaluationSliceResponse(
                as_of=slice_.as_of,
                observation_count=slice_.observation_count,
                mean_value=slice_.mean_value,
                median_value=slice_.median_value,
                stddev_value=slice_.stddev_value,
                minimum_value=slice_.minimum_value,
                maximum_value=slice_.maximum_value,
                range_value=slice_.range_value,
            )
            for slice_ in evaluation.cross_sections
        ],
    )
