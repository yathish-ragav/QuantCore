from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError
from quantcore.core.production_data_policy import ProductionDataPolicy

from .fred import FREDClient
from .macro_provider import MacroDataProvider


class MacroProviderFactory:
    """Resolve the configured macroeconomic data provider."""

    @staticmethod
    def get_provider() -> MacroDataProvider:
        provider = settings.macro_data_provider.strip().lower()
        ProductionDataPolicy.validate_macro_provider(provider)
        if provider == "fred":
            return FREDClient()
        raise ConfigurationError(f"Unknown macro data provider: {provider}")
