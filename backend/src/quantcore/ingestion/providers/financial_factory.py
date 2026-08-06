from .sec import SECProvider


class FinancialProviderFactory:

    @staticmethod
    def get_provider():
        return SECProvider()