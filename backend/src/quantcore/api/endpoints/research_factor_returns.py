from datetime import timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import (
    get_price_service,
    get_research_factor_cross_sectional_service,
    get_research_factor_panel_service,
    get_research_factor_return_service,
    get_research_historical_analysis_service,
)
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_factor_returns import (
    ResearchFactorReturnRequest,
    ResearchFactorReturnResponse,
    ResearchFactorReturnRowResponse,
)
from quantcore.services.price_service import PriceService
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_factor_return_service import ResearchFactorReturnService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)


router = APIRouter(
    prefix="/api/v1/research/factors",
    tags=["Research Factor Returns"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_FACTOR_RETURN_ROWS = 1000


def _normalize_price_observations(observations):
    """Adapt DB price timestamps to the timezone-aware research contract."""
    normalized = []
    for observation in observations:
        date = observation.date
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        normalized.append(
            SimpleNamespace(
                date=date,
                close=observation.close,
                adjusted_close=observation.adjusted_close,
            )
        )
    return tuple(normalized)


@router.post(
    "/returns",
    response_model=ResearchFactorReturnResponse,
)
def build_research_factor_returns(
    request: ResearchFactorReturnRequest,
    historical_service: ResearchHistoricalAnalysisService = Depends(
        get_research_historical_analysis_service
    ),
    panel_service: ResearchFactorPanelService = Depends(
        get_research_factor_panel_service
    ),
    cross_sectional_service: ResearchFactorCrossSectionalService = Depends(
        get_research_factor_cross_sectional_service
    ),
    return_service: ResearchFactorReturnService = Depends(
        get_research_factor_return_service
    ),
    price_service: PriceService = Depends(get_price_service),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_FACTOR_RETURN_ROWS:
        raise InvalidInputError(
            "Research factor return request exceeds the maximum of "
            f"{MAX_FACTOR_RETURN_ROWS} symbol/as-of rows."
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

    symbols_by_security: dict[int, str] = {}
    for row in ranked_panel.rows:
        symbols_by_security.setdefault(row.security_id, row.symbol)

    price_history_by_security = {
        security_id: _normalize_price_observations(
            price_service.get_price_history(symbol)
        )
        for security_id, symbol in symbols_by_security.items()
    }

    result = return_service.compute_forward_returns(
        ranked_panel,
        price_history_by_security,
        horizon=request.horizon,
        return_price_basis=request.return_price_basis,
    )

    return ResearchFactorReturnResponse(
        factor_key=result.factor_key,
        definition_version=result.definition_version,
        dataset_fingerprint=dataset.dataset_fingerprint,
        dataset_identity=dataset.dataset_identity,
        horizon=result.horizon,
        return_price_basis=result.return_price_basis,
        entry_policy=result.entry_policy,
        ranking=ranked_panel.ranking,
        higher_is_better=ranked_panel.higher_is_better,
        row_count=len(result.rows),
        rows=[
            ResearchFactorReturnRowResponse(
                symbol=row.symbol,
                security_id=row.security_id,
                factor_as_of=row.factor_as_of,
                value_numeric=row.factor_value.value_numeric,
                value_text=row.factor_value.value_text,
                unit=row.factor_value.unit,
                input_manifest=(
                    dict(row.factor_value.input_manifest)
                    if row.factor_value.input_manifest is not None
                    else None
                ),
                factor_rank=row.factor_rank,
                normalized_rank=row.normalized_rank,
                entry_date=row.entry_date,
                exit_date=row.exit_date,
                entry_price=row.entry_price,
                exit_price=row.exit_price,
                forward_return=row.forward_return,
                return_price_basis=row.return_price_basis,
                status=row.status,
            )
            for row in result.rows
        ],
    )
