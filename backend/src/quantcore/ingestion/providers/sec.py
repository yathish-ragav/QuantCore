from .financial_provider import FinancialDataProvider


class SECProvider(FinancialDataProvider):

    def get_income_statements(
        self,
        symbol: str,
    ):
        raise NotImplementedError(
            "SEC provider not implemented yet."
        )