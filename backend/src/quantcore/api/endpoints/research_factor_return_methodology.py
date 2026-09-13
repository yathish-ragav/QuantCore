from datetime import timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends

from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.api.dependencies import (
    get_price_service,
    get_research_factor_cross_sectional_service,
    get_research_factor_panel_service,
    get_research_factor_return_methodology_service,
    get_research_factor_return_service,
    get_research_historical_analysis_service,
)
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.research_factor_return_methodology import (
    ResearchFactorReturnBucketResponse,
    ResearchFactorReturnMethodologyRequest,
    ResearchFactorReturnMethodologyResponse,
    ResearchFactorReturnSliceResponse,
)
from quantcore.services.price_service import PriceService
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_factor_return_methodology_service import (
    ResearchFactorReturnMethodologyService,
)
from quantcore.services.research_factor_return_service import ResearchFactorReturnService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)


router = APIRouter(
    prefix="/api/v1/research/factors",
    tags=["Research Factor Return Methodology"],
    dependencies=[Depends(require_scopes(RESEARCH_READ_SCOPE))],
)

MAX_FACTOR_RETURN_METHODOLOGY_ROWS = 1000


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
    "/returns/series",
    response_model=ResearchFactorReturnMethodologyResponse,
)
def build_research_factor_return_series(
    request: ResearchFactorReturnMethodologyRequest,
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
    methodology_service: ResearchFactorReturnMethodologyService = Depends(
        get_research_factor_return_methodology_service
    ),
    price_service: PriceService = Depends(get_price_service),
):
    requested_rows = len(request.symbols) * len(request.as_ofs)
    if requested_rows > MAX_FACTOR_RETURN_METHODOLOGY_ROWS:
        raise InvalidInputError(
            "Research factor return methodology request exceeds the maximum of "
            f"{MAX_FACTOR_RETURN_METHODOLOGY_ROWS} symbol/as-of rows."
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

    return_panel = return_service.compute_forward_returns(
        ranked_panel,
        price_history_by_security,
        horizon=request.horizon,
        return_price_basis=request.return_price_basis,
    )
    series = methodology_service.compute_factor_return_series(
        return_panel,
        bucket_count=request.bucket_count,
        minimum_observations_per_leg=request.minimum_observations_per_leg,
    )

    return ResearchFactorReturnMethodologyResponse(
        factor_key=series.factor_key,
        definition_version=series.definition_version,
        dataset_fingerprint=dataset.dataset_fingerprint,
        dataset_identity=dataset.dataset_identity,
        horizon=series.horizon,
        return_price_basis=series.return_price_basis,
        bucket_count=series.bucket_count,
        weighting=series.weighting,
        long_bucket=series.long_bucket,
        short_bucket=series.short_bucket,
        construction=series.construction,
        row_count=len(series.slices),
        slices=[
            ResearchFactorReturnSliceResponse(
                as_of=slice_.as_of,
                total_observation_count=slice_.total_observation_count,
                eligible_observation_count=slice_.eligible_observation_count,
                long_bucket=slice_.long_bucket,
                short_bucket=slice_.short_bucket,
                long_return=slice_.long_return,
                short_return=slice_.short_return,
                long_short_return=slice_.long_short_return,
                status=slice_.status,
                buckets=[
                    ResearchFactorReturnBucketResponse(
                        bucket_number=bucket.bucket_number,
                        observation_count=bucket.observation_count,
                        eligible_return_count=bucket.eligible_return_count,
                        mean_forward_return=bucket.mean_forward_return,
                    )
                    for bucket in slice_.buckets
                ],
            )
            for slice_ in series.slices
        ],
    )
