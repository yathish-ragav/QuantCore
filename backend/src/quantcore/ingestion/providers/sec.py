from datetime import date, datetime
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
from quantcore.schemas.sec_filing import SECFilingData
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData

from .financial_provider import FinancialDataProvider
from .regulatory_provider import RegulatoryDataProvider


class SECProvider(FinancialDataProvider, RegulatoryDataProvider):
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

    def get_sec_filings(
        self,
        cik: str,
    ) -> list[SECFilingData]:
        """Retrieve SEC EDGAR filing metadata for the issuer.

        The submissions API provides the current filing history and references
        additional JSON files when the issuer has older filings. QuantCore
        follows those references so the normalized dataset can represent the
        issuer's complete available EDGAR filing history rather than only the
        most recent year/1,000 filings. Filing documents themselves are not
        downloaded by this method.
        """

        cik = cik.strip()
        if not cik:
            raise InvalidInputError("CIK must not be empty.")

        if not cik.isdigit() or len(cik) > 10:
            raise InvalidInputError("CIK must be a numeric SEC CIK.")

        cik = f"{int(cik):010d}"
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"

        try:
            response = requests.get(
                url,
                headers=self.HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve SEC filing metadata."
            ) from exc

        if not isinstance(data, dict):
            raise DataValidationError(
                "SEC submissions response must be an object."
            )

        filing_rows = []
        filings = data.get("filings", {})
        if not isinstance(filings, dict):
            raise DataValidationError(
                "SEC submissions 'filings' field must be an object."
            )

        recent = filings.get("recent")
        if isinstance(recent, dict):
            filing_rows.extend(self._submission_rows(recent))

        files = filings.get("files", [])
        if not isinstance(files, list):
            raise DataValidationError(
                "SEC submissions 'files' field must be a list."
            )

        for file_info in files:
            if not isinstance(file_info, dict):
                continue

            name = file_info.get("name")
            if not isinstance(name, str) or not name.strip():
                continue

            historical_url = f"{self.BASE_URL}/submissions/{name}"
            try:
                historical_response = requests.get(
                    historical_url,
                    headers=self.HEADERS,
                    timeout=30,
                )
                historical_response.raise_for_status()
                historical_data = historical_response.json()
            except requests.RequestException as exc:
                raise ExternalDataError(
                    "Failed to retrieve historical SEC filing metadata."
                ) from exc

            if not isinstance(historical_data, dict):
                raise DataValidationError(
                    "SEC historical submissions response must be an object."
                )

            historical_filings = historical_data.get("filings", {})
            if not isinstance(historical_filings, dict):
                raise DataValidationError(
                    "SEC historical submissions 'filings' field must be an object."
                )

            historical_recent = historical_filings.get("recent")
            if isinstance(historical_recent, dict):
                filing_rows.extend(
                    self._submission_rows(historical_recent)
                )

        normalized: list[SECFilingData] = []
        for row in filing_rows:
            try:
                normalized.append(
                    self._normalize_submission_row(
                        row,
                        cik=cik,
                    )
                )
            except (TypeError, ValueError, KeyError) as exc:
                raise DataValidationError(
                    "Invalid SEC filing metadata row."
                ) from exc

        return normalized

    @staticmethod
    def _submission_rows(recent: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert SEC's columnar submissions structure into row dictionaries."""

        columns = list(recent.keys())
        lengths = [
            len(value)
            for value in recent.values()
            if isinstance(value, list)
        ]
        if not lengths:
            return []

        row_count = max(lengths)
        rows: list[dict[str, Any]] = []
        for index in range(row_count):
            row = {}
            for column in columns:
                values = recent.get(column)
                row[column] = (
                    values[index]
                    if isinstance(values, list) and index < len(values)
                    else None
                )
            rows.append(row)
        return rows

    @staticmethod
    def _parse_submission_date(value: Any):
        if value in (None, ""):
            return None
        return date.fromisoformat(str(value))

    @staticmethod
    def _parse_acceptance_datetime(value: Any):
        if value in (None, ""):
            return None
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)

    @classmethod
    def _normalize_submission_row(
        cls,
        row: dict[str, Any],
        *,
        cik: str,
    ) -> SECFilingData:
        accession = str(row.get("accessionNumber") or "").strip()
        filing_date = cls._parse_submission_date(row.get("filingDate"))
        form = str(row.get("form") or "").strip()

        if not accession or filing_date is None or not form:
            raise ValueError("Missing required SEC filing identity fields.")

        primary_document = row.get("primaryDocument")
        accession_no_dash = accession.replace("-", "")
        archive_base = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession_no_dash}"
        )
        filing_url = (
            f"{archive_base}/{primary_document}"
            if primary_document
            else f"{archive_base}/{accession}-index.html"
        )

        return SECFilingData(
            accession_number=accession,
            filing_date=filing_date,
            report_date=cls._parse_submission_date(
                row.get("reportDate")
            ),
            acceptance_datetime=cls._parse_acceptance_datetime(
                row.get("acceptanceDateTime")
            ),
            form=form,
            act=row.get("act"),
            file_number=row.get("fileNumber"),
            film_number=row.get("filmNumber"),
            items=row.get("items"),
            primary_document=primary_document,
            primary_doc_description=row.get("primaryDocDescription"),
            is_xbrl=bool(row.get("isXBRL", False)),
            is_inline_xbrl=bool(row.get("isInlineXBRL", False)),
            fiscal_year=(
                int(row["fiscalYear"])
                if row.get("fiscalYear") is not None
                else None
            ),
            fiscal_period=row.get("fiscalPeriod"),
            is_amendment=form.endswith("/A"),
            filing_url=filing_url,
        )

    def get_sec_xbrl_fact_observations(
        self,
        cik: str,
    ) -> list[SECXBRLFactObservationData]:
        """Retrieve raw SEC CompanyFacts observations without collapsing revisions."""
        from decimal import Decimal, InvalidOperation

        cik = cik.strip()
        if not cik:
            raise InvalidInputError("CIK must not be empty.")
        if not cik.isdigit() or len(cik) > 10:
            raise InvalidInputError("CIK must be a numeric SEC CIK.")
        cik = f"{int(cik):010d}"

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
                "Failed to retrieve SEC XBRL fact observations."
            ) from exc

        if not isinstance(data, dict):
            raise DataValidationError("SEC CompanyFacts response must be an object.")
        facts = data.get("facts")
        if not isinstance(facts, dict):
            raise DataValidationError("SEC CompanyFacts 'facts' field must be an object.")

        observations: list[SECXBRLFactObservationData] = []
        for taxonomy, taxonomy_facts in facts.items():
            if not isinstance(taxonomy, str) or not isinstance(taxonomy_facts, dict):
                continue
            for concept, fact_definition in taxonomy_facts.items():
                if not isinstance(concept, str) or not isinstance(fact_definition, dict):
                    continue
                units = fact_definition.get("units", {})
                if not isinstance(units, dict):
                    continue
                for unit, unit_facts in units.items():
                    if not isinstance(unit, str) or not isinstance(unit_facts, list):
                        continue
                    for raw in unit_facts:
                        if not isinstance(raw, dict):
                            continue
                        accession = str(raw.get("accn") or "").strip()
                        filed = raw.get("filed")
                        form = str(raw.get("form") or "").strip()
                        end = raw.get("end")
                        value = raw.get("val")
                        if not accession or not filed or not form or not end or value is None:
                            continue
                        try:
                            observation = SECXBRLFactObservationData(
                                taxonomy=taxonomy,
                                concept=concept,
                                unit=unit,
                                value=Decimal(str(value)),
                                period_start=(
                                    date.fromisoformat(str(raw["start"]))
                                    if raw.get("start") else None
                                ),
                                period_end=date.fromisoformat(str(end)),
                                filed_at=date.fromisoformat(str(filed)),
                                accession_number=accession,
                                form=form,
                                fiscal_year=(
                                    int(raw["fy"]) if raw.get("fy") is not None else None
                                ),
                                fiscal_period=(
                                    str(raw["fp"]) if raw.get("fp") is not None else None
                                ),
                                frame=(
                                    str(raw["frame"]) if raw.get("frame") is not None else ""
                                ),
                                qtrs=(
                                    int(raw["qtrs"]) if raw.get("qtrs") is not None else 0
                                ),
                                decimals=(
                                    str(raw["decimals"]) if raw.get("decimals") is not None else None
                                ),
                            )
                        except (TypeError, ValueError, InvalidOperation) as exc:
                            raise DataValidationError(
                                "Invalid SEC XBRL fact observation."
                            ) from exc
                        observations.append(observation)

        return observations

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