from sqlalchemy.orm import Session
from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError
from quantcore.core.production_data_policy import ProductionDataPolicy

from .regulatory_provider import RegulatoryDataProvider
from .sec import SECProvider


class RegulatoryProviderFactory:
    """Resolve the configured regulatory-data provider."""

    @staticmethod
    def get_provider(db: Session | None = None) -> RegulatoryDataProvider:
        provider = settings.regulatory_data_provider.strip().lower()
        ProductionDataPolicy.validate_regulatory_provider(provider)

        if provider == "sec":
            return SECProvider(
                company_facts_cache=SECProvider.cache_for_session(db) if db is not None else None
            )

        raise ConfigurationError(
            f"Unknown regulatory data provider: {provider}"
        )
