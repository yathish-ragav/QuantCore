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

    @classmethod
    def validate_financial_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "sec":
            raise ConfigurationError(
                "Production fundamental data must use SEC-derived observations."
            )

    @classmethod
    def validate_regulatory_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "sec":
            raise ConfigurationError(
                "Production regulatory data must use SEC EDGAR."
            )

    @classmethod
    def validate_macro_provider(cls, provider: str) -> None:
        if not cls._enabled():
            return
        if provider.strip().lower() != "fred":
            raise ConfigurationError(
                "Production macroeconomic data must use FRED."
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
