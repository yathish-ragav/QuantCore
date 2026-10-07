from pathlib import Path

from pydantic import Field
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
    # Production provider-rights attestations are deployment controls, not
    # legal determinations. They require an operator to record that the
    # deployed account/contract permits QuantCore's intended use.
    MASSIVE_DATA_LICENSE_CONFIRMED: bool = False
    MASSIVE_DATA_LICENSE_REFERENCE: str = ""
    FRED_DATA_TERMS_CONFIRMED: bool = False
    FRED_DATA_TERMS_REFERENCE: str = ""
    FRED_DATA_STORAGE_AUTHORIZED: bool = False
    FRED_DATA_STORAGE_REFERENCE: str = ""
    SEC_DATA_POLICY_CONFIRMED: bool = False
    SEC_DATA_POLICY_REFERENCE: str = ""
    QUANTCORE_INGESTION_SCHEDULES_JSON: str = ""

    market_data_provider: str = "yahoo"
    financial_data_provider: str = "fmp"
    regulatory_data_provider: str = "sec"
    realtime_market_data_provider: str = "fmp"
    macro_data_provider: str = "fred"
    SQL_ECHO: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    # Keep the default connection budget conservative across API workers and
    # the separately running ingestion worker/scheduler processes.
    DB_POOL_SIZE: int = Field(default=5, gt=0)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, gt=0)

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


settings = Settings()  # type: ignore[call-arg]  # Pydantic loads required fields from the environment.
