from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError
from quantcore.core.production_data_policy import ProductionDataPolicy
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.ingestion.providers.massive import MassiveClient
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
        ProductionDataPolicy.validate_realtime_provider(provider)

        if provider == "massive":
            return MassiveClient()

        if provider == "fmp":
            return FMPClient()

        raise ConfigurationError(
            f"Unknown real-time market data provider: {provider}"
        )
