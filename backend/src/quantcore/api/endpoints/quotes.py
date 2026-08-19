from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_quote_service
from quantcore.schemas.quote import QuoteData
from quantcore.services.quote_service import QuoteService


router = APIRouter(
    prefix="/quotes",
    tags=["Quotes"],
)


@router.get(
    "/{symbol}",
    response_model=QuoteData,
)
def get_quote(
    symbol: str,
    service: QuoteService = Depends(get_quote_service),
):
    return service.get_quote(symbol)
