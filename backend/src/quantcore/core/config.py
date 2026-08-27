from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str
    FMP_API_KEY: str

    market_data_provider: str = "yahoo"
    financial_data_provider: str = "fmp"
    regulatory_data_provider: str = "sec"
    realtime_market_data_provider: str = "fmp"
    SQL_ECHO: bool = False

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
    )


settings = Settings()