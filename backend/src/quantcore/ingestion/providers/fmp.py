import requests
from .base import MarketDataProvider
from quantcore.core.config import settings


class FMPClient(MarketDataProvider):
    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self):
        self.api_key = settings.FMP_API_KEY

    def get_income_statements(
        self,
        symbol: str,
        limit: int = 10,
    ):
        response = requests.get(
            f"{self.BASE_URL}/income-statement",
            params={
                "symbol": symbol,
                "limit": limit,
                "apikey": self.api_key,
            },
            timeout=30,
        )

        response.raise_for_status()

        return response.json()