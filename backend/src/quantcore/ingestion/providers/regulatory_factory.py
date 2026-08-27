from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError

from .regulatory_provider import RegulatoryDataProvider
from .sec import SECProvider


class RegulatoryProviderFactory:
    """Resolve the configured regulatory-data provider."""

    @staticmethod
    def get_provider() -> RegulatoryDataProvider:
        provider = settings.regulatory_data_provider.strip().lower()

        if provider == "sec":
            return SECProvider()

        raise ConfigurationError(
            f"Unknown regulatory data provider: {provider}"
        )
