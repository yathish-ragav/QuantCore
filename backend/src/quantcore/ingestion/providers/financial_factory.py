from .fmp import FMPClient


class FinancialProviderFactory:

    @staticmethod
    def get_provider():
        return FMPClient()