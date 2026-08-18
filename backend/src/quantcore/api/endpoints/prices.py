from fastapi import APIRouter, Depends

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
    service: PriceService = Depends(get_price_service),
):
    normalized_symbol = symbol.strip().upper()

    prices = service.get_price_history(
        normalized_symbol
    )

    return [
        PriceResponse(
            date=price.date,
            open=price.open,
            high=price.high,
            low=price.low,
            close=price.close,
            volume=price.volume,
            dividends=price.dividends,
            stock_splits=price.stock_splits,
        )
        for price in prices
    ]