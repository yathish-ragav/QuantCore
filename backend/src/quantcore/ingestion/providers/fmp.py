import requests

from quantcore.core.config import settings
from quantcore.schemas.income_statement import IncomeStatementData

from .financial_provider import FinancialDataProvider


class FMPClient(FinancialDataProvider):
    """Financial Modeling Prep data provider."""

    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self) -> None:
        self.api_key = settings.FMP_API_KEY

    def get_income_statements(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[IncomeStatementData]:
        if not symbol:
            raise ValueError("Symbol must not be empty.")

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")

        response = requests.get(
            f"{self.BASE_URL}/income-statement",
            params={
                "symbol": symbol,
                "limit": limit,
                "apikey": self.api_key,
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise ValueError(
                "FMP income statement response must be a list."
            )

        statements: list[IncomeStatementData] = []

        for item in data:
            if not isinstance(item, dict):
                raise ValueError(
                    "FMP income statement item must be an object."
                )

            statements.append(
                IncomeStatementData(
                    fiscal_date=item["date"],
                    total_revenue=item.get("revenue"),
                    gross_profit=item.get("grossProfit"),
                    operating_income=item.get("operatingIncome"),
                    net_income=item.get("netIncome"),
                    eps=item.get("eps"),
                    shares_outstanding=item.get(
                        "weightedAverageShsOut"
                    ),
                )
            )

        return statements