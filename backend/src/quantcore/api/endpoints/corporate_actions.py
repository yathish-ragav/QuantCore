from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.authorization import INGESTION_WRITE_SCOPE, require_scopes
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
    actions = service.get_actions(symbol.strip().upper(), as_of=as_of)
    return [
        CorporateActionResponse(
            effective_date=action.effective_date,
            action_type=action.action_type,
            amount=action.amount,
            split_ratio=action.split_ratio,
            related_security_id=getattr(action, "related_security_id", None),
            old_symbol=getattr(action, "old_symbol", None),
            new_symbol=getattr(action, "new_symbol", None),
            old_exchange=getattr(action, "old_exchange", None),
            new_exchange=getattr(action, "new_exchange", None),
        )
        for action in actions
    ]


@router.post(
    "/{symbol}/sync",
    dependencies=[Depends(require_scopes(INGESTION_WRITE_SCOPE))],
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
