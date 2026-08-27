from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_corporate_action_service
from quantcore.schemas.responses import CorporateActionResponse
from quantcore.services.corporate_action_service import (
    CorporateActionService,
    CorporateActionSyncResult,
)

router = APIRouter(
    prefix="/corporate-actions",
    tags=["Corporate Actions"],
)


@router.get(
    "/{symbol}",
    response_model=list[CorporateActionResponse],
)
def get_corporate_actions(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Return corporate actions known at this timestamp.",
    ),
    service: CorporateActionService = Depends(
        get_corporate_action_service
    ),
):
    return service.get_actions(symbol.strip().upper(), as_of=as_of)


@router.post(
    "/{symbol}/sync",
)
def sync_corporate_actions(
    symbol: str,
    service: CorporateActionService = Depends(
        get_corporate_action_service
    ),
):
    result = service.sync_corporate_actions(symbol.strip().upper())
    return {
        "symbol": symbol.strip().upper(),
        "actions_added": result.created,
        "actions_updated": result.updated,
        "actions_unchanged": result.unchanged,
        "actions_processed": result.records_processed,
    }
