import requests

from quantcore.core.config import settings
from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.income_statement import IncomeStatementData

from .financial_provider import FinancialDataProvider


class FMPClient(FinancialDataProvider):
    """
    Financial Modeling Prep data provider.

    This class is responsible only for communicating with FMP and
    transforming the provider response into QuantCore domain schemas.

    HTTP/network exceptions intentionally propagate from this layer.
    Application-level error translation is handled by higher layers.
    """

    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self) -> None:
        self.api_key = settings.FMP_API_KEY

    def get_income_statements(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[IncomeStatementData]:
        """
        Retrieve income statement data from Financial Modeling Prep.

        Parameters
        ----------
        symbol:
            Equity ticker symbol.

        limit:
            Maximum number of statements to retrieve.

        Returns
        -------
        list[IncomeStatementData]
            Normalized income statement records.

        Raises
        ------
        InvalidInputError
            If symbol or limit is invalid.

        requests.RequestException
            If the external HTTP request fails.

        ValueError
            If FMP returns data in an unexpected format.
        """

        # ---------------------------------------------------------
        # 1. Validate caller input.
        # ---------------------------------------------------------

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        if limit <= 0:
            raise InvalidInputError(
                "Limit must be greater than zero."
            )

        # ---------------------------------------------------------
        # 2. Call external provider.
        #
        # HTTP/network exceptions intentionally propagate.
        #
        # The provider layer should not translate transport
        # failures into application-level errors.
        # ---------------------------------------------------------

        response = requests.get(
            f"{self.BASE_URL}/income-statement",
            params={
                "symbol": symbol,
                "limit": limit,
                "apikey": self.api_key,
            },
            timeout=30,
        )

        # ---------------------------------------------------------
        # 3. Raise HTTP errors unchanged.
        #
        # This preserves requests.HTTPError semantics for callers
        # and keeps provider responsibilities clean.
        # ---------------------------------------------------------

        response.raise_for_status()

        # ---------------------------------------------------------
        # 4. Decode response.
        # ---------------------------------------------------------

        data = response.json()

        # ---------------------------------------------------------
        # 5. Validate provider response structure.
        # ---------------------------------------------------------

        if not isinstance(data, list):
            raise ValueError(
                "FMP income statement response must be a list."
            )

        # ---------------------------------------------------------
        # 6. Transform provider records into domain schemas.
        # ---------------------------------------------------------

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
                    operating_income=item.get(
                        "operatingIncome"
                    ),
                    net_income=item.get("netIncome"),
                    eps=item.get("eps"),
                    shares_outstanding=item.get(
                        "weightedAverageShsOut"
                    ),
                )
            )

        # ---------------------------------------------------------
        # 7. Return normalized domain objects.
        # ---------------------------------------------------------

        return statements