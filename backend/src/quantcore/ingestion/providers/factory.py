from quantcore.core.config import settings

from .yahoo import YahooClient
from .fmp import FMPClient


class ProviderFactory:

    @staticmethod
    def get_provider():
        provider = settings.market_data_provider.lower()

        if provider == "yahoo":
            return YahooClient()

        if provider == "fmp":
            return FMPClient()

        raise ValueError(f"Unknown provider: {provider}")