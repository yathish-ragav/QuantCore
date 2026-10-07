from quantcore.core.config import settings
from quantcore.core.exceptions import ConfigurationError


class ProductionDataPolicy:
    """Fail-closed provider policy for public/commercial deployments.

    Development and test environments retain provider configurability. In
    production, QuantCore requires the documented source stack:
      - SEC for issuer identity, filings, and XBRL fundamentals
      - Massive for market prices, corporate actions, quotes, and news
      - FRED for macroeconomic series
    """

    @staticmethod
    def _enabled() -> bool:
        # Production is always fail-closed. The enforcement flag remains a
        # required deployment assertion, but must never disable policy checks.
        return settings.ENVIRONMENT.strip().lower() == "production"

    @classmethod
    def _require_attestation(
        cls, *, provider: str, confirmed: bool, reference: str
    ) -> None:
        if not confirmed:
            raise ConfigurationError(
                f"Production {provider} data-use attestation is not confirmed."
            )
        if not reference.strip():
            raise ConfigurationError(
                f"Production {provider} data-use policy reference is required."
            )

    @classmethod
    def validate_market_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        normalized = provider.strip().lower()
        if normalized != "massive":
            raise ConfigurationError(
                "Production market data must use the licensed Massive provider."
            )
        if not settings.MASSIVE_API_KEY.strip():
            raise ConfigurationError(
                "MASSIVE_API_KEY is required for production market data."
            )
        cls._require_attestation(
            provider="Massive",
            confirmed=settings.MASSIVE_DATA_LICENSE_CONFIRMED,
            reference=settings.MASSIVE_DATA_LICENSE_REFERENCE,
        )

    @classmethod
    def validate_realtime_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        normalized = provider.strip().lower()
        if normalized != "massive":
            raise ConfigurationError(
                "Production realtime market data must use the licensed Massive provider."
            )
        if not settings.MASSIVE_API_KEY.strip():
            raise ConfigurationError(
                "MASSIVE_API_KEY is required for production realtime market data."
            )
        cls._require_attestation(
            provider="Massive",
            confirmed=settings.MASSIVE_DATA_LICENSE_CONFIRMED,
            reference=settings.MASSIVE_DATA_LICENSE_REFERENCE,
        )

    @classmethod
    def validate_financial_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "sec":
            raise ConfigurationError(
                "Production fundamental data must use SEC-derived observations."
            )
        cls._require_attestation(
            provider="SEC",
            confirmed=settings.SEC_DATA_POLICY_CONFIRMED,
            reference=settings.SEC_DATA_POLICY_REFERENCE,
        )

    @classmethod
    def validate_regulatory_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "sec":
            raise ConfigurationError("Production regulatory data must use SEC EDGAR.")
        cls._require_attestation(
            provider="SEC",
            confirmed=settings.SEC_DATA_POLICY_CONFIRMED,
            reference=settings.SEC_DATA_POLICY_REFERENCE,
        )

    @classmethod
    def validate_macro_storage(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "fred":
            return
        cls._require_attestation(
            provider="FRED storage",
            confirmed=settings.FRED_DATA_STORAGE_AUTHORIZED,
            reference=settings.FRED_DATA_STORAGE_REFERENCE,
        )

    @classmethod
    def validate_macro_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "fred":
            raise ConfigurationError("Production macroeconomic data must use FRED.")
        cls._require_attestation(
            provider="FRED",
            confirmed=settings.FRED_DATA_TERMS_CONFIRMED,
            reference=settings.FRED_DATA_TERMS_REFERENCE,
        )

    @classmethod
    def validate_all(cls) -> None:
        if not cls._enabled():
            return
        if not settings.PRODUCTION_DATA_POLICY_ENFORCED:
            raise ConfigurationError(
                "PRODUCTION_DATA_POLICY_ENFORCED must be true in production."
            )
        cls.validate_market_provider(settings.market_data_provider)
        cls.validate_realtime_provider(settings.realtime_market_data_provider)
        cls.validate_financial_provider(settings.financial_data_provider)
        cls.validate_regulatory_provider(settings.regulatory_data_provider)
        cls.validate_macro_provider(settings.macro_data_provider)
