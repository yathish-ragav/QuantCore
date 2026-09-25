from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str
    FMP_API_KEY: str = ""
    FRED_API_KEY: str = ""
    MASSIVE_API_KEY: str = ""
    # Massive Stocks Basic allows 5 API calls/minute. Keep ingestion and
    # reference-data requests below that account-level limit by default.
    # Paid plans can override these explicitly without a code change.
    MASSIVE_REQUEST_INTERVAL_SECONDS: float = 12.5
    MASSIVE_REFERENCE_REQUEST_INTERVAL_SECONDS: float = 12.5
    SEC_USER_AGENT: str = "QuantCore/1.0 contact: yathishragav@gmail.com"
    PRODUCTION_DATA_POLICY_ENFORCED: bool = True

    market_data_provider: str = "yahoo"
    financial_data_provider: str = "fmp"
    regulatory_data_provider: str = "sec"
    realtime_market_data_provider: str = "fmp"
    macro_data_provider: str = "fred"
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # Generic OIDC resource-server settings. Authentication is fail-closed
    # when these are not configured; no local token format is accepted.
    AUTH_ISSUER: str = ""
    AUTH_AUDIENCE: str = ""
    AUTH_JWKS_URL: str = ""
    AUTH_ALGORITHMS: str = "RS256"
    AUTH_JWKS_CACHE_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
    )


settings = Settings()