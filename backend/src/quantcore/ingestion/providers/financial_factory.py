from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError
from quantcore.core.production_data_policy import ProductionDataPolicy

from .financial_provider import FinancialDataProvider
from .fmp import FMPClient
from .sec import SECProvider


class FinancialProviderFactory:
    """Resolve the configured fundamental-data provider."""

    @staticmethod
    def get_provider() -> FinancialDataProvider:
        provider = settings.financial_data_provider.strip().lower()
        ProductionDataPolicy.validate_financial_provider(provider)

        if provider == "fmp":
            return FMPClient()

        if provider == "sec":
            return SECProvider()

        raise ConfigurationError(
            f"Unknown financial data provider: {provider}"
        )
