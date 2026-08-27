from datetime import date

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_macro_service
from quantcore.schemas.responses import MacroObservationResponse, MacroSeriesResponse, MacroSyncResponse
from quantcore.services.macro_service import MacroService


router = APIRouter(
    prefix="/macro",
    tags=["Macro Economics"],
)


@router.get(
    "/series/{series_id}",
    response_model=MacroSeriesResponse,
)
def get_macro_series(
    series_id: str,
    service: MacroService = Depends(get_macro_service),
):
    series = service.get_series(series_id)
    return MacroSeriesResponse.model_validate(series, from_attributes=True)


@router.get(
    "/series/{series_id}/observations",
    response_model=list[MacroObservationResponse],
)
def get_macro_observations(
    series_id: str,
    as_of: date | None = Query(default=None),
    service: MacroService = Depends(get_macro_service),
):
    observations = service.get_observations(series_id, as_of=as_of)
    return [
        MacroObservationResponse(
            observation_date=item.observation_date,
            value=float(item.value) if item.value is not None else None,
            realtime_start=item.realtime_start,
            realtime_end=item.realtime_end,
            vintage_date=item.vintage_date,
        )
        for item in observations
    ]


@router.post(
    "/series/{series_id}/sync",
    response_model=MacroSyncResponse,
)
def sync_macro_series(
    series_id: str,
    vintage_date: date | None = Query(default=None),
    service: MacroService = Depends(get_macro_service),
):
    result = service.sync_series(series_id, vintage_date=vintage_date)
    return MacroSyncResponse(
        series_id=series_id.strip().upper(),
        created=result.created,
        unchanged=result.unchanged,
        records_processed=result.records_processed,
        vintage_date=result.vintage_date,
    )
