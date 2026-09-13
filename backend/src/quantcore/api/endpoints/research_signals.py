from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import (
    get_research_factor_cross_sectional_service,
    get_research_factor_panel_service,
    get_research_historical_analysis_service,
    get_research_signal_service,
)
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_signals import (
    ResearchSignalContributionResponse,
    ResearchSignalFactorResponse,
    ResearchSignalRequest,
    ResearchSignalResponse,
    ResearchSignalRowResponse,
)
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)
from quantcore.services.research_signal_service import (
    ResearchSignalDefinition,
    ResearchSignalService,
)


router = APIRouter(
    prefix="/api/v1/research/signals",
    tags=["Research Signals"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_RESEARCH_SIGNAL_ROWS = 1000
MAX_RESEARCH_SIGNAL_FACTORS = 16


@router.post(
    "",
    response_model=ResearchSignalResponse,
)
def build_research_signal(
    request: ResearchSignalRequest,
    historical_service: ResearchHistoricalAnalysisService = Depends(
        get_research_historical_analysis_service
    ),
    panel_service: ResearchFactorPanelService = Depends(
        get_research_factor_panel_service
    ),
    cross_sectional_service: ResearchFactorCrossSectionalService = Depends(
        get_research_factor_cross_sectional_service
    ),
    signal_service: ResearchSignalService = Depends(get_research_signal_service),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_RESEARCH_SIGNAL_ROWS:
        raise InvalidInputError(
            "Research signal request exceeds the maximum of "
            f"{MAX_RESEARCH_SIGNAL_ROWS} symbol/as-of rows."
        )
    if len(request.factors) > MAX_RESEARCH_SIGNAL_FACTORS:
        raise InvalidInputError(
            "Research signal request exceeds the maximum of "
            f"{MAX_RESEARCH_SIGNAL_FACTORS} factors."
        )

    definition = ResearchSignalDefinition(
        signal_key=request.signal_key,
        definition_version=request.signal_definition_version,
        factor_identities=tuple(
            (factor.factor_key, factor.definition_version)
            for factor in request.factors
        ),
        weights=tuple(factor.weight for factor in request.factors),
        description=request.description,
    )

    dataset = historical_service.build_historical_dataset(
        request.symbols,
        as_ofs=request.as_ofs,
        definition_identities=request.definition_identities,
        dataset_identity=request.dataset_identity,
    )

    panels_by_factor = {}
    for factor in request.factors:
        panel = panel_service.build_factor_panel(
            dataset,
            factor_key=factor.factor_key,
            definition_version=factor.definition_version,
        )
        panels_by_factor[(factor.factor_key.strip(), factor.definition_version.strip())] = (
            cross_sectional_service.rank_factor_panel(
                panel,
                higher_is_better=factor.higher_is_better,
            )
        )

    signal = signal_service.construct_signal(definition, panels_by_factor)

    return ResearchSignalResponse(
        signal_key=signal.signal_key,
        definition_version=signal.definition_version,
        description=definition.description,
        dataset_fingerprint=dataset.dataset_fingerprint,
        dataset_identity=dataset.dataset_identity,
        factor_count=len(signal.factor_identities),
        factors=[
            ResearchSignalFactorResponse(
                factor_key=factor.factor_key.strip(),
                definition_version=factor.definition_version.strip(),
                weight=factor.weight,
                higher_is_better=factor.higher_is_better,
            )
            for factor in request.factors
        ],
        construction=signal.construction,
        row_count=len(signal.rows),
        rows=[
            ResearchSignalRowResponse(
                symbol=row.symbol,
                security_id=row.security_id,
                as_of=row.as_of,
                score=row.score,
                centered_score=row.centered_score,
                contributions=[
                    ResearchSignalContributionResponse(
                        factor_key=contribution.factor_key,
                        definition_version=contribution.definition_version,
                        normalized_rank=contribution.normalized_rank,
                        weight=contribution.weight,
                        weighted_contribution=contribution.weighted_contribution,
                    )
                    for contribution in row.contributions
                ],
            )
            for row in signal.rows
        ],
    )
