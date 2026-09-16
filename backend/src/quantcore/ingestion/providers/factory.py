from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError
from quantcore.core.production_data_policy import ProductionDataPolicy

from .base import MarketDataProvider
from .massive import MassiveClient
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
        ProductionDataPolicy.validate_market_provider(provider)

        if provider == "massive":
            return MassiveClient()

        if provider == "yahoo":
            return YahooClient()

        raise ConfigurationError(
            f"Unknown market data provider: {provider}"
        )