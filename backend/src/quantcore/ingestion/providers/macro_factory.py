from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError

from .fred import FREDClient
from .macro_provider import MacroDataProvider


class MacroProviderFactory:
    """Resolve the configured macroeconomic data provider."""

    @staticmethod
    def get_provider() -> MacroDataProvider:
        provider = settings.macro_data_provider.strip().lower()
        if provider == "fred":
            return FREDClient()
        raise ConfigurationError(f"Unknown macro data provider: {provider}")
