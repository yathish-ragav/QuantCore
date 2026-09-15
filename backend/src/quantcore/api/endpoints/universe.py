from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from quantcore.api.dependencies import get_universe_sync_service
from quantcore.services.universe_sync_service import UniverseSyncService


class UniverseCoverageResponse(BaseModel):
    active_companies: int
    active_securities: int
    inactive_securities: int


class UniverseSyncRunResponse(BaseModel):
    id: int
    source: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    records_processed: int
    active_companies: int
    active_securities: int
    inactive_securities: int
    error: str | None


class UniverseStatusResponse(BaseModel):
    latest_run: UniverseSyncRunResponse | None
    coverage: UniverseCoverageResponse


router = APIRouter(prefix="/universe", tags=["Universe"])


def _run_response(run) -> UniverseSyncRunResponse:
    return UniverseSyncRunResponse(
        id=run.id,
        source=run.source,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        records_processed=run.records_processed,
        active_companies=run.active_companies,
        active_securities=run.active_securities,
        inactive_securities=run.inactive_securities,
        error=run.error,
    )


@router.get("/status", response_model=UniverseStatusResponse)
def get_universe_status(
    service: UniverseSyncService = Depends(get_universe_sync_service),
):
    latest_run, coverage = service.get_status()
    return UniverseStatusResponse(
        latest_run=_run_response(latest_run) if latest_run else None,
        coverage=UniverseCoverageResponse(**coverage),
    )
