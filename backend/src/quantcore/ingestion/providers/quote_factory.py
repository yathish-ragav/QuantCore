from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.ingestion.providers.quote_provider import QuoteProvider


class QuoteProviderFactory:
    """Resolve the configured real-time quote provider."""

    @staticmethod
    def get_provider() -> QuoteProvider:
        provider = (
            settings.realtime_market_data_provider
            .strip()
            .lower()
        )

        if provider == "fmp":
            return FMPClient()

        raise ConfigurationError(
            f"Unknown real-time market data provider: {provider}"
        )
