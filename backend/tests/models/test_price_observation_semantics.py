from datetime import datetime

from quantcore.core.enums import PriceBasis
from quantcore.schemas.price import PriceData


def test_price_data_defaults_to_explicit_unadjusted_basis():
    data = PriceData(
        date=datetime(2026, 1, 2),
        open=100.0,
        high=110.0,
        low=95.0,
        close=108.0,
        volume=1_000_000,
        adjusted_close=107.5,
    )

    assert data.price_basis is PriceBasis.UNADJUSTED
    assert data.adjusted_close == 107.5
