from datetime import date
from typing import Any

import requests

from quantcore.core.enums import FinancialPeriodType
from quantcore.core.exceptions import (
    DataValidationError,
    ExternalDataError,
    InvalidInputError,
)
from quantcore.schemas.balance_sheet import BalanceSheetData
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData

from .financial_provider import FinancialDataProvider


class SECProvider(FinancialDataProvider):
    SOURCE = "SEC"
    """
    SEC EDGAR XBRL financial data provider.

    This provider is responsible for communicating with SEC EDGAR
    and translating external transport failures into QuantCore
    application-level exceptions.
    """

    BASE_URL = "https://data.sec.gov"
    TICKER_URL = "https://www.sec.gov/files/company_tickers.json"

    HEADERS = {
        "User-Agent": "QuantCore/1.0 contact: yathishragav@gmail.com",
        "Accept-Encoding": "gzip, deflate",
    }

    _ticker_to_cik: dict[str, str] | None = None

    def _load_ticker_map(self) -> dict[str, str]:
        """
        Load the SEC's official ticker -> CIK mapping.

        The mapping is cached for the lifetime of the process.

        External network failures are translated into
        ExternalDataError so that lower-level requests exceptions
        do not leak through the provider boundary.
        """

        if SECProvider._ticker_to_cik is not None:
            return SECProvider._ticker_to_cik

        try:
            response = requests.get(
                self.TICKER_URL,
                headers=self.HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve SEC ticker mapping."
            ) from exc

        if not isinstance(data, dict):
            raise DataValidationError(
                "SEC ticker mapping response must be an object."
            )

        mapping: dict[str, str] = {}

        try:
            for company in data.values():
                if not isinstance(company, dict):
                    continue

                ticker = company.get("ticker")
                cik = company.get("cik_str")

                if not ticker or cik is None:
                    continue

                mapping[str(ticker).upper()] = f"{int(cik):010d}"
        except (TypeError, ValueError) as exc:
            raise DataValidationError(
                "Invalid SEC ticker mapping data."
            ) from exc

        SECProvider._ticker_to_cik = mapping

        return mapping

    def _get_cik(self, symbol: str) -> str:
        """
        Resolve a ticker symbol to its SEC CIK.

        Unknown symbols are treated as invalid client input.
        """

        symbol = symbol.upper().strip()

        mapping = self._load_ticker_map()

        try:
            return mapping[symbol]

        except KeyError as exc:
            raise InvalidInputError(
                f"SEC CIK not found for ticker: {symbol}"
            ) from exc

    def get_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]:
        """
        Retrieve annual income statements from SEC XBRL CompanyFacts.
        """

        # -------------------------------------------------
        # 1. Validate caller input.
        # -------------------------------------------------
        symbol = symbol.strip()

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        # -------------------------------------------------
        # 2. Resolve ticker -> SEC CIK.
        # -------------------------------------------------
        cik = self._get_cik(symbol)

        # -------------------------------------------------
        # 3. Retrieve CompanyFacts from SEC.
        #
        # Transport/provider failures are translated into
        # an application-level ExternalDataError.
        # -------------------------------------------------
        try:
            response = requests.get(
                f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve income statement data from SEC."
            ) from exc

        # -------------------------------------------------
        # 4. Extract US GAAP facts.
        # -------------------------------------------------
        if not isinstance(data, dict):
            raise DataValidationError(
                "SEC CompanyFacts response must be an object."
            )

        facts = data.get("facts", {})
        if not isinstance(facts, dict):
            raise DataValidationError(
                "SEC CompanyFacts 'facts' field must be an object."
            )

        us_gaap = facts.get("us-gaap", {})
        if not isinstance(us_gaap, dict):
            raise DataValidationError(
                "SEC CompanyFacts us-gaap data must be an object."
            )

        revenue = self._get_fact(
            us_gaap,
            [
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            ],
            preferred_unit="USD",
        )

        gross_profit = self._get_fact(
            us_gaap,
            ["GrossProfit"],
            preferred_unit="USD",
        )

        operating_income = self._get_fact(
            us_gaap,
            ["OperatingIncomeLoss"],
            preferred_unit="USD",
        )

        net_income = self._get_fact(
            us_gaap,
            [
                "NetIncomeLoss",
                "ProfitLoss",
            ],
            preferred_unit="USD",
        )

        eps = self._get_fact(
            us_gaap,
            [
                "EarningsPerShareDiluted",
                "EarningsPerShareBasic",
            ],
            preferred_unit="USD-per-shares",
        )

        shares = self._get_fact(
            us_gaap,
            [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfSharesOutstandingBasic",
            ],
            preferred_unit="shares",
        )

        # -------------------------------------------------
        # 5. Determine annual fiscal dates from revenue.
        # -------------------------------------------------
        fiscal_dates = self._get_fiscal_dates(
            revenue
        )

        # -------------------------------------------------
        # 6. Build normalized domain objects.
        # -------------------------------------------------
        statements: list[IncomeStatementData] = []

        for fiscal_date in fiscal_dates:
            statements.append(
                IncomeStatementData(
                    fiscal_date=fiscal_date,
                    **self._metadata_on_date(
                        revenue,
                        fiscal_date,
                        period_type=FinancialPeriodType.ANNUAL,
                    ),
                    total_revenue=self._value_on_date(
                        revenue,
                        fiscal_date,
                    ),
                    gross_profit=self._value_on_date(
                        gross_profit,
                        fiscal_date,
                    ),
                    operating_income=self._value_on_date(
                        operating_income,
                        fiscal_date,
                    ),
                    net_income=self._value_on_date(
                        net_income,
                        fiscal_date,
                    ),
                    eps=self._value_on_date(
                        eps,
                        fiscal_date,
                    ),
                    shares_outstanding=self._integer_value_on_date(
                        shares,
                        fiscal_date,
                    ),
                )
            )

        return statements

    def get_cash_flow_statements(
        self,
        symbol: str,
    ) -> list[CashFlowStatementData]:
        """
        Retrieve annual cash flow statements from SEC XBRL CompanyFacts.
        """

        # -------------------------------------------------
        # 1. Validate caller input.
        # -------------------------------------------------
        symbol = symbol.strip()

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        # -------------------------------------------------
        # 2. Resolve ticker -> SEC CIK.
        # -------------------------------------------------
        cik = self._get_cik(symbol)

        # -------------------------------------------------
        # 3. Retrieve CompanyFacts from SEC.
        # -------------------------------------------------
        try:
            response = requests.get(
                f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve cash flow statement data from SEC."
            ) from exc

        # -------------------------------------------------
        # 4. Extract US GAAP facts.
        # -------------------------------------------------
        if not isinstance(data, dict):
            raise DataValidationError(
                "SEC CompanyFacts response must be an object."
            )

        facts = data.get("facts", {})
        if not isinstance(facts, dict):
            raise DataValidationError(
                "SEC CompanyFacts 'facts' field must be an object."
            )

        us_gaap = facts.get("us-gaap", {})
        if not isinstance(us_gaap, dict):
            raise DataValidationError(
                "SEC CompanyFacts us-gaap data must be an object."
            )

        operating_cash_flow = self._get_fact(
            us_gaap,
            [
                "NetCashProvidedByUsedInOperatingActivities",
                "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            ],
            preferred_unit="USD",
        )

        # SEC reports capital expenditure as a positive outflow
        # figure (unlike FMP, which reports it as negative). This
        # sign difference is intentional and handled below when
        # deriving free cash flow.
        capital_expenditure = self._get_fact(
            us_gaap,
            [
                "PaymentsToAcquirePropertyPlantAndEquipment",
                "PaymentsForCapitalImprovements",
            ],
            preferred_unit="USD",
        )

        investing_cash_flow = self._get_fact(
            us_gaap,
            ["NetCashProvidedByUsedInInvestingActivities"],
            preferred_unit="USD",
        )

        financing_cash_flow = self._get_fact(
            us_gaap,
            ["NetCashProvidedByUsedInFinancingActivities"],
            preferred_unit="USD",
        )

        depreciation_and_amortization = self._get_fact(
            us_gaap,
            [
                "DepreciationDepletionAndAmortization",
                "DepreciationAmortizationAndAccretionNet",
            ],
            preferred_unit="USD",
        )

        stock_based_compensation = self._get_fact(
            us_gaap,
            ["ShareBasedCompensation"],
            preferred_unit="USD",
        )

        dividends_paid = self._get_fact(
            us_gaap,
            [
                "PaymentsOfDividends",
                "PaymentsOfDividendsCommonStock",
            ],
            preferred_unit="USD",
        )

        share_repurchases = self._get_fact(
            us_gaap,
            ["PaymentsForRepurchaseOfCommonStock"],
            preferred_unit="USD",
        )

        net_change_in_cash = self._get_fact(
            us_gaap,
            [
                "CashAndCashEquivalentsPeriodIncreaseDecrease",
                "CashCashEquivalentsRestrictedCashAndRestrictedCash"
                "EquivalentsPeriodIncreaseDecreaseIncludingExchange"
                "RateEffect",
            ],
            preferred_unit="USD",
        )

        # -------------------------------------------------
        # 5. Determine annual fiscal dates from operating cash flow.
        # -------------------------------------------------
        fiscal_dates = self._get_fiscal_dates(
            operating_cash_flow
        )

        # -------------------------------------------------
        # 6. Build normalized domain objects.
        # -------------------------------------------------
        statements: list[CashFlowStatementData] = []

        for fiscal_date in fiscal_dates:

            ocf_value = self._value_on_date(
                operating_cash_flow,
                fiscal_date,
            )
            capex_value = self._value_on_date(
                capital_expenditure,
                fiscal_date,
            )

            free_cash_flow = (
                ocf_value - capex_value
                if ocf_value is not None
                and capex_value is not None
                else None
            )

            statements.append(
                CashFlowStatementData(
                    fiscal_date=fiscal_date,
                    **self._metadata_on_date(
                        operating_cash_flow,
                        fiscal_date,
                        period_type=FinancialPeriodType.ANNUAL,
                    ),
                    operating_cash_flow=ocf_value,
                    capital_expenditure=capex_value,
                    free_cash_flow=free_cash_flow,
                    investing_cash_flow=self._value_on_date(
                        investing_cash_flow,
                        fiscal_date,
                    ),
                    financing_cash_flow=self._value_on_date(
                        financing_cash_flow,
                        fiscal_date,
                    ),
                    depreciation_and_amortization=self._value_on_date(
                        depreciation_and_amortization,
                        fiscal_date,
                    ),
                    stock_based_compensation=self._value_on_date(
                        stock_based_compensation,
                        fiscal_date,
                    ),
                    dividends_paid=self._value_on_date(
                        dividends_paid,
                        fiscal_date,
                    ),
                    share_repurchases=self._value_on_date(
                        share_repurchases,
                        fiscal_date,
                    ),
                    net_change_in_cash=self._value_on_date(
                        net_change_in_cash,
                        fiscal_date,
                    ),
                )
            )

        return statements

    def get_balance_sheets(
        self,
        symbol: str,
    ) -> list[BalanceSheetData]:
        """Retrieve annual balance sheets from SEC XBRL CompanyFacts."""

        symbol = symbol.strip()

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        cik = self._get_cik(symbol)

        try:
            response = requests.get(
                f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.HEADERS,
                timeout=30,
            )

            response.raise_for_status()
            data = response.json()

        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve balance sheet data from SEC."
            ) from exc

        if not isinstance(data, dict):
            raise DataValidationError(
                "SEC CompanyFacts response must be an object."
            )

        facts = data.get("facts", {})
        if not isinstance(facts, dict):
            raise DataValidationError(
                "SEC CompanyFacts 'facts' field must be an object."
            )

        us_gaap = facts.get("us-gaap", {})
        if not isinstance(us_gaap, dict):
            raise DataValidationError(
                "SEC CompanyFacts us-gaap data must be an object."
            )

        cash = self._get_fact(
            us_gaap,
            ["CashAndCashEquivalentsAtCarryingValue"],
            preferred_unit="USD",
        )
        short_term_investments = self._get_fact(
            us_gaap,
            [
                "ShortTermInvestments",
                "MarketableSecuritiesCurrent",
            ],
            preferred_unit="USD",
        )
        accounts_receivable = self._get_fact(
            us_gaap,
            [
                "AccountsReceivableNetCurrent",
                "AccountsReceivableNet",
            ],
            preferred_unit="USD",
        )
        inventory = self._get_fact(
            us_gaap,
            ["InventoryNet"],
            preferred_unit="USD",
        )
        total_current_assets = self._get_fact(
            us_gaap,
            ["AssetsCurrent"],
            preferred_unit="USD",
        )
        property_plant_equipment_net = self._get_fact(
            us_gaap,
            [
                "PropertyPlantAndEquipmentNet",
                "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
            ],
            preferred_unit="USD",
        )
        goodwill = self._get_fact(
            us_gaap,
            ["Goodwill"],
            preferred_unit="USD",
        )
        intangible_assets = self._get_fact(
            us_gaap,
            [
                "FiniteLivedIntangibleAssetsNet",
                "IntangibleAssetsNetExcludingGoodwill",
            ],
            preferred_unit="USD",
        )
        total_assets = self._get_fact(
            us_gaap,
            ["Assets"],
            preferred_unit="USD",
        )

        accounts_payable = self._get_fact(
            us_gaap,
            ["AccountsPayableCurrent"],
            preferred_unit="USD",
        )
        short_term_debt = self._get_fact(
            us_gaap,
            [
                "ShortTermBorrowings",
                "ShortTermDebtCurrent",
                "LongTermDebtCurrent",
            ],
            preferred_unit="USD",
        )
        total_current_liabilities = self._get_fact(
            us_gaap,
            ["LiabilitiesCurrent"],
            preferred_unit="USD",
        )
        long_term_debt = self._get_fact(
            us_gaap,
            [
                "LongTermDebtNoncurrent",
                "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            ],
            preferred_unit="USD",
        )
        total_liabilities = self._get_fact(
            us_gaap,
            ["Liabilities"],
            preferred_unit="USD",
        )
        total_equity = self._get_fact(
            us_gaap,
            [
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                "StockholdersEquity",
            ],
            preferred_unit="USD",
        )
        retained_earnings = self._get_fact(
            us_gaap,
            ["RetainedEarningsAccumulatedDeficit"],
            preferred_unit="USD",
        )

        anchor = total_assets or total_current_assets or total_liabilities
        fiscal_dates = self._get_fiscal_dates(anchor)

        statements: list[BalanceSheetData] = []

        for fiscal_date in fiscal_dates:
            cash_value = self._value_on_date(cash, fiscal_date)
            sti_value = self._value_on_date(
                short_term_investments, fiscal_date
            )
            std_value = self._value_on_date(
                short_term_debt, fiscal_date
            )
            ltd_value = self._value_on_date(
                long_term_debt, fiscal_date
            )
            total_debt = None
            if std_value is not None or ltd_value is not None:
                total_debt = (std_value or 0) + (ltd_value or 0)

            net_debt = (
                total_debt - (cash_value or 0)
                if total_debt is not None
                else None
            )

            current_assets_value = self._value_on_date(
                total_current_assets, fiscal_date
            )
            current_liabilities_value = self._value_on_date(
                total_current_liabilities, fiscal_date
            )
            working_capital = (
                current_assets_value - current_liabilities_value
                if current_assets_value is not None
                and current_liabilities_value is not None
                else None
            )

            statements.append(
                BalanceSheetData(
                    fiscal_date=fiscal_date,
                    **self._metadata_on_date(
                        anchor,
                        fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    cash_and_cash_equivalents=cash_value,
                    short_term_investments=sti_value,
                    accounts_receivable=self._value_on_date(
                        accounts_receivable, fiscal_date
                    ),
                    inventory=self._value_on_date(
                        inventory, fiscal_date
                    ),
                    total_current_assets=current_assets_value,
                    property_plant_equipment_net=self._value_on_date(
                        property_plant_equipment_net, fiscal_date
                    ),
                    goodwill=self._value_on_date(
                        goodwill, fiscal_date
                    ),
                    intangible_assets=self._value_on_date(
                        intangible_assets, fiscal_date
                    ),
                    total_assets=self._value_on_date(
                        total_assets, fiscal_date
                    ),
                    accounts_payable=self._value_on_date(
                        accounts_payable, fiscal_date
                    ),
                    short_term_debt=std_value,
                    total_current_liabilities=current_liabilities_value,
                    long_term_debt=ltd_value,
                    total_liabilities=self._value_on_date(
                        total_liabilities, fiscal_date
                    ),
                    total_equity=self._value_on_date(
                        total_equity, fiscal_date
                    ),
                    retained_earnings=self._value_on_date(
                        retained_earnings, fiscal_date
                    ),
                    total_debt=total_debt,
                    net_debt=net_debt,
                    working_capital=working_capital,
                )
            )

        return statements

    @staticmethod
    def _get_fact(
        us_gaap: dict[str, Any],
        tags: list[str],
        preferred_unit: str,
    ) -> list[dict[str, Any]]:
        """
        Find the first available XBRL fact using the preferred unit.
        """

        for tag in tags:
            fact = us_gaap.get(tag)

            if not fact:
                continue

            units = fact.get("units", {})

            if preferred_unit in units:
                return units[preferred_unit]

            if units:
                return next(iter(units.values()))

        return []

    @staticmethod
    def _is_annual_fact(
        fact: dict[str, Any],
    ) -> bool:
        """
        Determine whether an XBRL fact represents an annual 10-K result.
        """

        return (
            fact.get("form") in {"10-K", "10-K/A"}
            and fact.get("fp") == "FY"
        )

    @classmethod
    def _metadata_on_date(
        cls,
        facts: list[dict[str, Any]],
        fiscal_date: date,
        *,
        period_type: FinancialPeriodType,
    ) -> dict[str, Any]:
        """Return the latest filed annual XBRL identity for a period end."""

        matching = [
            fact
            for fact in facts
            if cls._is_annual_fact(fact)
            and fact.get("end") == fiscal_date.isoformat()
        ]

        if not matching:
            return {
                "period_type": period_type,
            }

        latest = max(
            matching,
            key=lambda fact: fact.get("filed", ""),
        )

        def _parse_date(value):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except (TypeError, ValueError):
                return None

        return {
            "period_start": (
                _parse_date(latest.get("start"))
                if period_type is not FinancialPeriodType.INSTANT
                else None
            ),
            "fiscal_year": latest.get("fy"),
            "fiscal_period": latest.get("fp"),
            "period_type": period_type,
            "filing_date": _parse_date(latest.get("filed")),
            "filing_form": latest.get("form"),
            "accession_number": latest.get("accn"),
        }

    @classmethod
    def _get_fiscal_dates(
        cls,
        facts: list[dict[str, Any]],
    ) -> list[date]:
        """
        Extract unique annual fiscal year-end dates.
        """

        dates: set[date] = set()

        for fact in facts:
            if not cls._is_annual_fact(fact):
                continue

            end = fact.get("end")

            if not end:
                continue

            dates.add(
                date.fromisoformat(end)
            )

        return sorted(dates)

    @classmethod
    def _value_on_date(
        cls,
        facts: list[dict[str, Any]],
        fiscal_date: date,
    ) -> float | None:
        """
        Get the latest filed annual value for a fiscal date.
        """

        matching_facts: list[dict[str, Any]] = []

        for fact in facts:
            if not cls._is_annual_fact(fact):
                continue

            if fact.get("end") != fiscal_date.isoformat():
                continue

            if fact.get("val") is None:
                continue

            matching_facts.append(fact)

        if not matching_facts:
            return None

        latest = max(
            matching_facts,
            key=lambda fact: fact.get("filed", ""),
        )

        return float(latest["val"])

    @classmethod
    def _integer_value_on_date(
        cls,
        facts: list[dict[str, Any]],
        fiscal_date: date,
    ) -> int | None:
        """
        Get an annual value and convert it to an integer.
        """

        value = cls._value_on_date(
            facts,
            fiscal_date,
        )

        if value is None:
            return None

        return int(value)