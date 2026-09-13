from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import get_research_historical_analysis_service
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_datasets import (
    ResearchHistoricalDatasetRequest,
    ResearchHistoricalDatasetResponse,
    ResearchHistoricalDatasetRowResponse,
)
from quantcore.schemas.responses import ResearchFeatureResponse, ResearchFeatureVectorResponse
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)


router = APIRouter(
    prefix="/api/v1/research/datasets",
    tags=["Research Datasets"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_HISTORICAL_DATASET_ROWS = 1000


def _feature_vector_response(vector) -> ResearchFeatureVectorResponse:
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


@router.post(
    "/historical",
    response_model=ResearchHistoricalDatasetResponse,
)
def build_research_historical_dataset(
    request: ResearchHistoricalDatasetRequest,
    service: ResearchHistoricalAnalysisService = Depends(
        get_research_historical_analysis_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_HISTORICAL_DATASET_ROWS:
        raise InvalidInputError(
            "Historical research dataset request exceeds the maximum of "
            f"{MAX_HISTORICAL_DATASET_ROWS} symbol/as-of rows."
        )

    dataset = service.build_historical_dataset(
        request.symbols,
        as_ofs=request.as_ofs,
        definition_identities=request.definition_identities,
        dataset_identity=request.dataset_identity,
    )

    return ResearchHistoricalDatasetResponse(
        dataset_fingerprint=dataset.dataset_fingerprint,
        definition_identities=(
            list(dataset.definition_identities)
            if dataset.definition_identities is not None
            else None
        ),
        dataset_identity=dataset.dataset_identity,
        row_count=len(dataset.rows),
        rows=[
            ResearchHistoricalDatasetRowResponse(
                symbol=row.symbol,
                security_id=row.security_id,
                as_of=row.as_of,
                feature_vector=_feature_vector_response(
                    row.feature_vector
                ).model_dump(mode="json"),
            )
            for row in dataset.rows
        ],
    )
