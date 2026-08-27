from datetime import datetime, timezone

import requests
from pydantic import ValidationError

from quantcore.core.config import settings
from quantcore.core.enums import FinancialPeriodType
from quantcore.core.exceptions import (
    DataValidationError,
    ExternalDataError,
    InvalidInputError,
)
from quantcore.schemas.balance_sheet import BalanceSheetData
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

    @staticmethod
    def _statement_metadata(
        item: dict,
        *,
        period_type: FinancialPeriodType,
    ) -> dict:
        """Extract non-destructive temporal metadata from an FMP row."""

        fiscal_date = item["date"]
        calendar_year = item.get("calendarYear")
        fiscal_year = int(calendar_year) if calendar_year is not None else int(
            str(fiscal_date)[:4]
        )

        return {
            "fiscal_year": fiscal_year,
            "fiscal_period": item.get("period") or (
                "FY" if period_type is FinancialPeriodType.ANNUAL else None
            ),
            "period_type": period_type,
            "filing_date": item.get("filingDate") or item.get("fillingDate"),
            "filing_form": item.get("form"),
            "accession_number": item.get("acceptedAccessionNumber")
            or item.get("accessionNumber"),
        }

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
                        **self._statement_metadata(
                            item,
                            period_type=FinancialPeriodType.ANNUAL,
                        ),
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
                        **self._statement_metadata(
                            item,
                            period_type=FinancialPeriodType.ANNUAL,
                        ),
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

    def get_balance_sheets(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[BalanceSheetData]:
        """Retrieve annual balance sheet data from FMP."""

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        if limit <= 0:
            raise InvalidInputError(
                "Limit must be greater than zero."
            )

        try:
            response = requests.get(
                f"{self.BASE_URL}/balance-sheet-statement",
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
                "Failed to retrieve balance sheet data "
                "from Financial Modeling Prep."
            ) from exc

        if not isinstance(data, list):
            raise DataValidationError(
                "FMP balance sheet response must be a list."
            )

        statements: list[BalanceSheetData] = []

        for item in data:
            if not isinstance(item, dict):
                raise DataValidationError(
                    "FMP balance sheet item must be an object."
                )

            try:
                cash = item.get("cashAndCashEquivalents")
                short_term_investments = item.get(
                    "shortTermInvestments"
                )
                short_term_debt = item.get("shortTermDebt")
                long_term_debt = item.get("longTermDebt")

                total_debt = item.get("totalDebt")
                if total_debt is None and (
                    short_term_debt is not None
                    or long_term_debt is not None
                ):
                    total_debt = (
                        (short_term_debt or 0)
                        + (long_term_debt or 0)
                    )

                net_debt = item.get("netDebt")
                if net_debt is None and total_debt is not None:
                    net_debt = total_debt - (cash or 0)

                current_assets = item.get("totalCurrentAssets")
                current_liabilities = item.get(
                    "totalCurrentLiabilities"
                )
                working_capital = item.get("workingCapital")
                if (
                    working_capital is None
                    and current_assets is not None
                    and current_liabilities is not None
                ):
                    working_capital = (
                        current_assets - current_liabilities
                    )

                statements.append(
                    BalanceSheetData(
                        fiscal_date=item["date"],
                        **self._statement_metadata(
                            item,
                            period_type=FinancialPeriodType.INSTANT,
                        ),
                        cash_and_cash_equivalents=cash,
                        short_term_investments=short_term_investments,
                        accounts_receivable=(
                            item.get("accountReceivables")
                            if item.get("accountReceivables") is not None
                            else (
                                item.get("accountsReceivables")
                                if item.get("accountsReceivables") is not None
                                else item.get("accountsReceivable")
                            )
                        ),
                        inventory=item.get("inventory"),
                        total_current_assets=current_assets,
                        property_plant_equipment_net=item.get(
                            "propertyPlantEquipmentNet"
                        ),
                        goodwill=item.get("goodwill"),
                        intangible_assets=item.get(
                            "intangibleAssets"
                        ),
                        total_assets=item.get("totalAssets"),
                        accounts_payable=(
                            item.get("accountPayables")
                            if item.get("accountPayables") is not None
                            else item.get("accountsPayable")
                        ),
                        short_term_debt=short_term_debt,
                        total_current_liabilities=current_liabilities,
                        long_term_debt=long_term_debt,
                        total_liabilities=item.get(
                            "totalLiabilities"
                        ),
                        total_equity=(
                            item.get("totalStockholdersEquity")
                            if item.get("totalStockholdersEquity")
                            is not None
                            else item.get("totalEquity")
                        ),
                        retained_earnings=item.get(
                            "retainedEarnings"
                        ),
                        total_debt=total_debt,
                        net_debt=net_debt,
                        working_capital=working_capital,
                    )
                )

            except (KeyError, TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid FMP balance sheet item."
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
