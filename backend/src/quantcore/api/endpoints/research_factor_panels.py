from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import (
    get_research_factor_panel_service,
    get_research_historical_analysis_service,
)
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_factor_panels import (
    ResearchFactorPanelRequest,
    ResearchFactorPanelResponse,
    ResearchFactorPanelRowResponse,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)


router = APIRouter(
    prefix="/api/v1/research/factors",
    tags=["Research Factor Panels"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_FACTOR_PANEL_ROWS = 1000


@router.post(
    "/panel",
    response_model=ResearchFactorPanelResponse,
)
def build_research_factor_panel(
    request: ResearchFactorPanelRequest,
    historical_service: ResearchHistoricalAnalysisService = Depends(
        get_research_historical_analysis_service
    ),
    panel_service: ResearchFactorPanelService = Depends(
        get_research_factor_panel_service
    ),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_FACTOR_PANEL_ROWS:
        raise InvalidInputError(
            "Research factor panel request exceeds the maximum of "
            f"{MAX_FACTOR_PANEL_ROWS} symbol/as-of rows."
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

    return ResearchFactorPanelResponse(
        factor_key=panel.factor_key,
        definition_version=panel.definition_version,
        dataset_fingerprint=dataset.dataset_fingerprint,
        dataset_identity=dataset.dataset_identity,
        unit=panel.unit,
        row_count=len(panel.rows),
        rows=[
            ResearchFactorPanelRowResponse(
                symbol=row.symbol,
                security_id=row.security_id,
                as_of=row.as_of,
                value_numeric=row.factor_value.value_numeric,
                value_text=row.factor_value.value_text,
                unit=row.factor_value.unit,
                input_manifest=(
                    dict(row.factor_value.input_manifest)
                    if row.factor_value.input_manifest is not None
                    else None
                ),
            )
            for row in panel.rows
        ],
    )
