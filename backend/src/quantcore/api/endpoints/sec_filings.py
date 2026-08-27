from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_sec_filing_service
from quantcore.schemas.responses import (
    FilingEventResponse,
    SECFilingResponse,
    SECFilingSyncResponse,
)
from quantcore.services.sec_filing_service import SECFilingService


router = APIRouter(
    prefix="/sec-filings",
    tags=["SEC Filings"],
)


@router.get(
    "/{symbol}",
    response_model=list[SECFilingResponse],
)
def get_sec_filings(
    symbol: str,
    service: SECFilingService = Depends(get_sec_filing_service),
):
    normalized_symbol = symbol.strip().upper()
    return service.get_filings(normalized_symbol)


@router.get(
    "/{symbol}/events",
    response_model=list[FilingEventResponse],
)
def get_sec_filing_events(
    symbol: str,
    service: SECFilingService = Depends(get_sec_filing_service),
):
    normalized_symbol = symbol.strip().upper()
    events = service.get_filing_events(normalized_symbol)
    return [
        FilingEventResponse(
            accession_number=event.filing.accession_number,
            event_type=event.event_type.value,
            occurred_at=event.occurred_at,
        )
        for event in events
    ]


@router.post(
    "/{symbol}/sync",
    response_model=SECFilingSyncResponse,
)
def sync_sec_filings(
    symbol: str,
    service: SECFilingService = Depends(get_sec_filing_service),
):
    normalized_symbol = symbol.strip().upper()
    result = service.sync_filings(normalized_symbol)
    return SECFilingSyncResponse(
        symbol=normalized_symbol,
        filings_added=result.created,
        filings_updated=result.updated,
        filings_unchanged=result.unchanged,
        filings_processed=result.records_processed,
        events_added=result.events_created,
    )
