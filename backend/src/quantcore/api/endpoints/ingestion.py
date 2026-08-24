from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_ingestion_orchestrator
from quantcore.schemas.responses import IngestionFreshnessResponse
from quantcore.services.ingestion_orchestrator import IngestionOrchestrator


router = APIRouter(
    prefix="/ingestion",
    tags=["Ingestion"],
)


@router.get(
    "/{symbol}/freshness",
    response_model=list[IngestionFreshnessResponse],
)
def get_ingestion_freshness(
    symbol: str,
    service: IngestionOrchestrator = Depends(
        get_ingestion_orchestrator
    ),
):
    normalized_symbol = symbol.strip().upper()

    return [
        IngestionFreshnessResponse(
            dataset=view.dataset.value,
            scope=view.scope.value,
            last_attempt_at=view.last_attempt_at,
            last_success_at=view.last_success_at,
            last_success_source=view.last_success_source,
            last_success_records=view.last_success_records,
            consecutive_failures=view.consecutive_failures,
            last_error=view.last_error,
            is_fresh=view.is_fresh,
        )
        for view in service.get_freshness(normalized_symbol)
    ]
