from datetime import datetime, timezone

import requests
from pydantic import ValidationError

from quantcore.core.config import settings
from quantcore.core.exceptions import (
    DataValidationError,
    ExternalDataError,
    InvalidInputError,
)
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData
from quantcore.schemas.quote import QuoteData

from .financial_provider import FinancialDataProvider
from .quote_provider import QuoteProvider


class FMPClient(FinancialDataProvider, QuoteProvider):
    SOURCE = "FMP"
    """
    Financial Modeling Prep data provider.

    Responsibilities:
    - validate provider method input
    - communicate with FMP
    - translate transport failures into QuantCore errors
    - validate provider response structure
    - transform provider data into domain schemas
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
        Retrieve income statement data from FMP.

        Raises
        ------
        InvalidInputError
            Invalid caller input.

        ExternalDataError
            FMP could not be reached or returned an HTTP error.

        DataValidationError
            FMP returned malformed or unexpected data.
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
        # All requests-layer failures are translated here so they
        # cannot leak beyond the provider boundary.
        # ---------------------------------------------------------

        try:
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

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve income statement data "
                "from Financial Modeling Prep."
            ) from exc

        # ---------------------------------------------------------
        # 3. Validate top-level provider response.
        # ---------------------------------------------------------

        if not isinstance(data, list):
            raise DataValidationError(
                "FMP income statement response must be a list."
            )

        # ---------------------------------------------------------
        # 4. Transform provider records.
        # ---------------------------------------------------------

        statements: list[IncomeStatementData] = []

        for item in data:

            if not isinstance(item, dict):
                raise DataValidationError(
                    "FMP income statement item must be an object."
                )

            try:
                statements.append(
                    IncomeStatementData(
                        fiscal_date=item["date"],
                        total_revenue=item.get("revenue"),
                        gross_profit=item.get(
                            "grossProfit"
                        ),
                        operating_income=item.get(
                            "operatingIncome"
                        ),
                        net_income=item.get(
                            "netIncome"
                        ),
                        eps=item.get("eps"),
                        shares_outstanding=item.get(
                            "weightedAverageShsOut"
                        ),
                    )
                )

            except (KeyError, TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid FMP income statement item."
                ) from exc

        return statements

    def get_cash_flow_statements(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[CashFlowStatementData]:
        """
        Retrieve cash flow statement data from FMP.

        NOTE: field names below (operatingCashFlow, capitalExpenditure,
        freeCashFlow, etc.) are mapped against FMP's documented
        cash-flow-statement response shape. Verify against a live
        response / current FMP docs before relying on this in
        production — provider response shapes can change.

        Raises
        ------
        InvalidInputError
            Invalid caller input.

        ExternalDataError
            FMP could not be reached or returned an HTTP error.

        DataValidationError
            FMP returned malformed or unexpected data.
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
        # ---------------------------------------------------------

        try:
            response = requests.get(
                f"{self.BASE_URL}/cash-flow-statement",
                params={
                    "symbol": symbol,
                    "limit": limit,
                    "apikey": self.api_key,
                },
                timeout=30,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve cash flow statement data "
                "from Financial Modeling Prep."
            ) from exc

        # ---------------------------------------------------------
        # 3. Validate top-level provider response.
        # ---------------------------------------------------------

        if not isinstance(data, list):
            raise DataValidationError(
                "FMP cash flow statement response must be a list."
            )

        # ---------------------------------------------------------
        # 4. Transform provider records.
        # ---------------------------------------------------------

        statements: list[CashFlowStatementData] = []

        for item in data:

            if not isinstance(item, dict):
                raise DataValidationError(
                    "FMP cash flow statement item must be an object."
                )

            try:
                operating_cash_flow = item.get(
                    "operatingCashFlow"
                )
                capital_expenditure = item.get(
                    "capitalExpenditure"
                )
                free_cash_flow = item.get(
                    "freeCashFlow"
                )

                if (
                    free_cash_flow is None
                    and operating_cash_flow is not None
                    and capital_expenditure is not None
                ):
                    free_cash_flow = (
                        operating_cash_flow
                        + capital_expenditure
                    )

                statements.append(
                    CashFlowStatementData(
                        fiscal_date=item["date"],
                        operating_cash_flow=operating_cash_flow,
                        capital_expenditure=capital_expenditure,
                        free_cash_flow=free_cash_flow,
                        investing_cash_flow=item.get(
                            "netCashProvidedByInvestingActivities"
                        ),
                        financing_cash_flow=item.get(
                            "netCashProvidedByFinancingActivities"
                        ),
                        depreciation_and_amortization=item.get(
                            "depreciationAndAmortization"
                        ),
                        stock_based_compensation=item.get(
                            "stockBasedCompensation"
                        ),
                        dividends_paid=item.get(
                            "netDividendsPaid"
                        ),
                        share_repurchases=item.get(
                            "commonStockRepurchased"
                        ),
                        net_change_in_cash=item.get(
                            "netChangeInCash"
                        ),
                    )
                )

            except (KeyError, TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid FMP cash flow statement item."
                ) from exc

        return statements

    def get_quote(self, symbol: str) -> QuoteData:
        """Retrieve the current market quote for a symbol from FMP."""

        symbol = symbol.strip().upper()

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        try:
            response = requests.get(
                f"{self.BASE_URL}/quote",
                params={
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve quote data from "
                "Financial Modeling Prep."
            ) from exc

        if not isinstance(data, list) or not data:
            raise DataValidationError(
                "FMP quote response must be a non-empty list."
            )

        item = data[0]

        if not isinstance(item, dict):
            raise DataValidationError(
                "FMP quote item must be an object."
            )

        try:
            timestamp = item["timestamp"]
            quote_timestamp = (
                timestamp
                if isinstance(timestamp, datetime)
                else datetime.fromtimestamp(
                    float(timestamp),
                    tz=timezone.utc,
                )
            )

            return QuoteData(
                symbol=item["symbol"],
                name=item["name"],
                price=item["price"],
                change=item["change"],
                change_percent=item["changePercentage"],
                day_low=item.get("dayLow"),
                day_high=item.get("dayHigh"),
                year_low=item.get("yearLow"),
                year_high=item.get("yearHigh"),
                market_cap=item.get("marketCap"),
                price_avg_50=item.get("priceAvg50"),
                price_avg_200=item.get("priceAvg200"),
                volume=item.get("volume"),
                exchange=item.get("exchange"),
                open=item.get("open"),
                previous_close=item.get("previousClose"),
                timestamp=quote_timestamp,
                source="fmp",
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            ValidationError,
        ) as exc:
            raise DataValidationError(
                "Invalid FMP quote item."
            ) from exc
