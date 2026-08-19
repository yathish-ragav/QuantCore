from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError

from .base import MarketDataProvider
from .yahoo import YahooClient


class ProviderFactory:
    """
    Factory for market-data providers.

    Financial-data providers such as FMP are intentionally not
    registered here. They implement FinancialDataProvider and are
    resolved by FinancialProviderFactory instead.
    """

    @staticmethod
    def get_provider() -> MarketDataProvider:
        provider = settings.market_data_provider.strip().lower()

        if provider == "yahoo":
            return YahooClient()

        raise ConfigurationError(
            f"Unknown market data provider: {provider}"
        )