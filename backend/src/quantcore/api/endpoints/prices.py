from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_price_service
from quantcore.schemas.responses import PriceResponse
from quantcore.services.price_service import PriceService


router = APIRouter(
    prefix="/prices",
    tags=["Prices"],
)


@router.get(
    "/{symbol}",
    response_model=list[PriceResponse],
)
def get_prices(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Return the latest price revision known at this timestamp.",
    ),
    service: PriceService = Depends(get_price_service),
):
    normalized_symbol = symbol.strip().upper()

    if as_of is None:
        prices = service.get_price_history(
            normalized_symbol
        )
    else:
        prices = service.get_price_history_as_of(
            normalized_symbol,
            as_of,
        )

    return [
        PriceResponse(
            date=price.date,
            open=price.open,
            high=price.high,
            low=price.low,
            close=price.close,
            adjusted_close=price.adjusted_close,
            price_basis=price.price_basis,
            volume=price.volume,
            dividends=price.dividends,
            stock_splits=price.stock_splits,
        )
        for price in prices
    ]