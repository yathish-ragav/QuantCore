from datetime import date, datetime
from typing import Any

import requests

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
from quantcore.schemas.sec_filing import SECFilingData
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData

from .financial_provider import FinancialDataProvider
from .regulatory_provider import RegulatoryDataProvider


class SECCompanyFactsCache:
    """Request-scoped cache for one issuer's SEC CompanyFacts payload."""

    def __init__(self) -> None:
        self._payload: tuple[str, dict[str, Any]] | None = None

    def get(self, cik: str) -> dict[str, Any] | None:
        if self._payload is None or self._payload[0] != cik:
            return None
        return self._payload[1]

    def set(self, cik: str, payload: dict[str, Any]) -> None:
        self._payload = (cik, payload)

    def clear(self) -> None:
        self._payload = None


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
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }

    _ticker_to_cik: dict[str, str] | None = None

    def __init__(
        self,
        *,
        company_facts_cache: SECCompanyFactsCache | None = None,
        http_session: requests.Session | None = None,
    ) -> None:
        self._company_facts_cache = company_facts_cache or SECCompanyFactsCache()
        self._http_session = http_session

    @staticmethod
    def http_session_for_session(db) -> requests.Session:
        """Return the pooled HTTP session owned by one SQLAlchemy session."""
        key = "quantcore.sec_http_session"
        session = db.info.get(key)
        if session is None:
            session = requests.Session()
            db.info[key] = session
        return session

    @staticmethod
    def cache_for_session(db) -> SECCompanyFactsCache:
        """Return the CompanyFacts cache owned by one SQLAlchemy session."""
        key = "quantcore.sec_company_facts_cache"
        cache = db.info.get(key)
        if cache is None:
            cache = SECCompanyFactsCache()
            db.info[key] = cache
        return cache

    def _get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
    ) -> requests.Response:
        """GET through the request-scoped pool when available."""
        if self._http_session is not None:
            return self._http_session.get(
                url,
                headers=headers,
                timeout=timeout,
            )
        return requests.get(
            url,
            headers=headers,
            timeout=timeout,
        )

    def _get_company_facts(
        self,
        cik: str,
        *,
        error_message: str,
    ) -> dict[str, Any]:
        """Fetch one issuer CompanyFacts payload and reuse it for this issuer."""
        cached = self._company_facts_cache.get(cik)
        if cached is not None:
            return cached

        try:
            response = self._get(
                f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise ExternalDataError(error_message) from exc

        if not isinstance(data, dict):
            raise DataValidationError(
                "SEC CompanyFacts response must be an object."
            )

        self._company_facts_cache.set(cik, data)
        return data

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
            response = self._get(
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
            response = self._get(
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
                historical_response = self._get(
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

            # SEC continuation files use the submission columns at the
            # top level (unlike the main CIK submissions response, which
            # nests them under filings.recent). Keep support for the nested
            # shape as a defensive compatibility path for fixtures/variants.
            historical_filings = historical_data.get("filings")
            if isinstance(historical_filings, dict):
                historical_rows = historical_filings.get("recent")
            else:
                historical_rows = historical_data

            if not isinstance(historical_rows, dict):
                raise DataValidationError(
                    "SEC historical submissions response must contain filing rows."
                )

            filing_rows.extend(
                self._submission_rows(historical_rows)
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

        data = self._get_company_facts(
            cik,
            error_message="Failed to retrieve SEC XBRL fact observations.",
        )

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
                            filed_date = date.fromisoformat(str(filed))
                            period_end = date.fromisoformat(str(end))
                            period_start = (
                                date.fromisoformat(str(raw["start"]))
                                if raw.get("start") else None
                            )

                            # A reported SEC fact cannot describe a period that
                            # ends after the filing date. Treat this as provider
                            # corruption/invalid source data instead of allowing
                            # future observations into the PIT dataset.
                            if period_end > filed_date:
                                raise DataValidationError(
                                    "SEC XBRL fact period_end cannot be after filed_at."
                                )
                            if period_start is not None and period_start > period_end:
                                raise DataValidationError(
                                    "SEC XBRL fact period_start cannot be after period_end."
                                )

                            observation = SECXBRLFactObservationData(
                                taxonomy=taxonomy,
                                concept=concept,
                                unit=unit,
                                value=Decimal(str(value)),
                                period_start=period_start,
                                period_end=period_end,
                                filed_at=filed_date,
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
                        except DataValidationError:
                            raise
                        except (TypeError, ValueError, InvalidOperation) as exc:
                            raise DataValidationError(
                                "Invalid SEC XBRL fact observation."
                            ) from exc
                        observations.append(observation)

        return observations

    def get_income_statements(
        self,
        symbol: str,
        *,
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
    ) -> list[IncomeStatementData]:
        """Retrieve normalized income statements for one SEC period type."""

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
        data = self._get_company_facts(
            cik,
            error_message="Failed to retrieve income statement data from SEC.",
        )

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
        ifrs_full = facts.get("ifrs-full", {})
        if not isinstance(ifrs_full, dict):
            ifrs_full = {}

        revenue = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues",
                    "SalesRevenueNet",
                ]),
                (ifrs_full, ["Revenue", "RevenueFromContractsWithCustomers"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        gross_profit = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["GrossProfit"]),
                (ifrs_full, ["GrossProfit"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        operating_income = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["OperatingIncomeLoss"]),
                (ifrs_full, ["ProfitLossFromOperatingActivities"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        net_income = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["NetIncomeLoss", "ProfitLoss"]),
                (ifrs_full, ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        eps = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["EarningsPerShareDiluted", "EarningsPerShareBasic"]),
                (ifrs_full, [
                    "DilutedEarningsLossPerShare",
                    "BasicEarningsLossPerShare",
                    "DilutedEarningsLossPerShareFromContinuingOperations",
                    "BasicEarningsLossPerShareFromContinuingOperations",
                ]),
            ],
            preferred_unit="USD-per-shares",
            period_type=period_type,
        )

        dei = facts.get("dei", {})
        if not isinstance(dei, dict):
            dei = {}

        shares = self._get_fact(
            dei,
            ["EntityCommonStockSharesOutstanding"],
            preferred_unit="shares",
        )
        weighted_average_shares = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "WeightedAverageNumberOfDilutedSharesOutstanding",
                    "WeightedAverageNumberOfSharesOutstandingBasic",
                ]),
                (ifrs_full, ["WeightedAverageNumberOfOrdinarySharesOutstanding"]),
            ],
            preferred_unit="shares",
            period_type=period_type,
        )

        # -------------------------------------------------
        # 5. Determine annual fiscal dates from every available
        # income-statement fact. Revenue is not a universal anchor:
        # some valid SEC issuers expose operating/net income without
        # one of the revenue concepts above. Never discard an entire
        # statement merely because one concept is absent.
        # -------------------------------------------------
        fiscal_dates = self._get_fiscal_dates_from_groups(
            revenue,
            gross_profit,
            operating_income,
            net_income,
            eps,
            weighted_average_shares,
            period_type=period_type,
        )

        # -------------------------------------------------
        # 6. Build normalized domain objects.
        # -------------------------------------------------
        statements: list[IncomeStatementData] = []

        for fiscal_date in fiscal_dates:
            statements.append(
                IncomeStatementData(
                    fiscal_date=fiscal_date,
                    **self._metadata_on_date_from_groups(
                        revenue, gross_profit, operating_income, net_income, eps,
                        weighted_average_shares, fiscal_date=fiscal_date,
                        period_type=period_type,
                    ),
                    total_revenue=self._value_on_date(
                        revenue,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    gross_profit=self._value_on_date(
                        gross_profit,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    operating_income=self._value_on_date(
                        operating_income,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    net_income=self._value_on_date(
                        net_income,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    eps=self._value_on_date(
                        eps,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    shares_outstanding=self._integer_value_on_date(
                        shares,
                        fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    weighted_average_shares_outstanding=(
                        self._integer_value_on_date(
                            weighted_average_shares,
                            fiscal_date,
                        )
                    ),
                )
            )

        return statements

    def get_cash_flow_statements(
        self,
        symbol: str,
        *,
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
    ) -> list[CashFlowStatementData]:
        """Retrieve normalized cash-flow statements for one SEC period type."""

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
        data = self._get_company_facts(
            cik,
            error_message="Failed to retrieve cash flow statement data from SEC.",
        )

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
        ifrs_full = facts.get("ifrs-full", {})
        if not isinstance(ifrs_full, dict):
            ifrs_full = {}

        operating_cash_flow = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "NetCashProvidedByUsedInOperatingActivities",
                    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
                ]),
                (ifrs_full, ["CashFlowsFromUsedInOperatingActivities"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        # SEC reports capital expenditure as a positive outflow
        # figure (unlike FMP, which reports it as negative). This
        # sign difference is intentional and handled below when
        # deriving free cash flow.
        capital_expenditure = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "PaymentsToAcquirePropertyPlantAndEquipment",
                    "PaymentsForCapitalImprovements",
                ]),
                (ifrs_full, ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        investing_cash_flow = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["NetCashProvidedByUsedInInvestingActivities"]),
                (ifrs_full, ["CashFlowsFromUsedInInvestingActivities"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        financing_cash_flow = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["NetCashProvidedByUsedInFinancingActivities"]),
                (ifrs_full, ["CashFlowsFromUsedInFinancingActivities"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        depreciation_and_amortization = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "DepreciationDepletionAndAmortization",
                    "DepreciationAmortizationAndAccretionNet",
                ]),
                (ifrs_full, ["DepreciationDepletionAndAmortisation", "DepreciationAndAmortisation"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        stock_based_compensation = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["ShareBasedCompensation"]),
                (ifrs_full, ["ShareBasedPayments"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        dividends_paid = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "PaymentsOfDividends",
                    "PaymentsOfDividendsCommonStock",
                ]),
                (ifrs_full, ["DividendsPaid"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        share_repurchases = self._get_fact_from_taxonomies(
            [
                (us_gaap, ["PaymentsForRepurchaseOfCommonStock"]),
                (ifrs_full, ["PaymentsForRepurchaseOfOrdinaryShares"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        net_change_in_cash = self._get_fact_from_taxonomies(
            [
                (us_gaap, [
                    "CashAndCashEquivalentsPeriodIncreaseDecrease",
                    "CashCashEquivalentsRestrictedCashAndRestrictedCash"
                    "EquivalentsPeriodIncreaseDecreaseIncludingExchange"
                    "RateEffect",
                ]),
                (ifrs_full, ["IncreaseDecreaseInCashAndCashEquivalents"]),
            ],
            preferred_unit="USD",
            period_type=period_type,
        )

        # -------------------------------------------------
        # 5. Determine annual fiscal dates from every available cash-flow
        # fact. Operating cash flow is preferred when present, but it is
        # not a universal anchor for every SEC issuer.
        # -------------------------------------------------
        fiscal_dates = self._get_fiscal_dates_from_groups(
            operating_cash_flow,
            capital_expenditure,
            investing_cash_flow,
            financing_cash_flow,
            depreciation_and_amortization,
            stock_based_compensation,
            dividends_paid,
            share_repurchases,
            net_change_in_cash,
            period_type=period_type,
        )

        # -------------------------------------------------
        # 6. Build normalized domain objects.
        # -------------------------------------------------
        statements: list[CashFlowStatementData] = []

        for fiscal_date in fiscal_dates:

            ocf_value = self._value_on_date(
                operating_cash_flow,
                fiscal_date,
                period_type=period_type,
            )
            capex_value = self._value_on_date(
                capital_expenditure,
                fiscal_date,
                period_type=period_type,
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
                    **self._metadata_on_date_from_groups(
                        operating_cash_flow, capital_expenditure, investing_cash_flow,
                        financing_cash_flow, depreciation_and_amortization,
                        stock_based_compensation, dividends_paid, share_repurchases,
                        net_change_in_cash, fiscal_date=fiscal_date,
                        period_type=period_type,
                    ),
                    operating_cash_flow=ocf_value,
                    capital_expenditure=capex_value,
                    free_cash_flow=free_cash_flow,
                    investing_cash_flow=self._value_on_date(
                        investing_cash_flow,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    financing_cash_flow=self._value_on_date(
                        financing_cash_flow,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    depreciation_and_amortization=self._value_on_date(
                        depreciation_and_amortization,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    stock_based_compensation=self._value_on_date(
                        stock_based_compensation,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    dividends_paid=self._value_on_date(
                        dividends_paid,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    share_repurchases=self._value_on_date(
                        share_repurchases,
                        fiscal_date,
                        period_type=period_type,
                    ),
                    net_change_in_cash=self._value_on_date(
                        net_change_in_cash,
                        fiscal_date,
                        period_type=period_type,
                    ),
                )
            )

        return statements

    def get_quarterly_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]:
        return self.get_income_statements(
            symbol,
            period_type=FinancialPeriodType.QUARTERLY,
        )

    def get_quarterly_cash_flow_statements(
        self,
        symbol: str,
    ) -> list[CashFlowStatementData]:
        return self.get_cash_flow_statements(
            symbol,
            period_type=FinancialPeriodType.QUARTERLY,
        )

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

        data = self._get_company_facts(
            cik,
            error_message="Failed to retrieve balance sheet data from SEC.",
        )

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
        ifrs_full = facts.get("ifrs-full", {})
        if not isinstance(ifrs_full, dict):
            ifrs_full = {}

        cash = self._get_fact_from_taxonomies(
            [(us_gaap, ["CashAndCashEquivalentsAtCarryingValue"]),
             (ifrs_full, ["CashAndCashEquivalents"])],
            preferred_unit="USD",
        )
        short_term_investments = self._get_fact_from_taxonomies(
            [(us_gaap, ["ShortTermInvestments", "MarketableSecuritiesCurrent"]),
             (ifrs_full, ["OtherCurrentFinancialAssets"])],
            preferred_unit="USD",
        )
        accounts_receivable = self._get_fact_from_taxonomies(
            [(us_gaap, ["AccountsReceivableNetCurrent", "AccountsReceivableNet"]),
             (ifrs_full, ["TradeAndOtherCurrentReceivables"])],
            preferred_unit="USD",
        )
        inventory = self._get_fact_from_taxonomies(
            [(us_gaap, ["InventoryNet"]), (ifrs_full, ["Inventories"])],
            preferred_unit="USD",
        )
        total_current_assets = self._get_fact_from_taxonomies(
            [(us_gaap, ["AssetsCurrent"]), (ifrs_full, ["CurrentAssets"])],
            preferred_unit="USD",
        )
        property_plant_equipment_net = self._get_fact_from_taxonomies(
            [(us_gaap, [
                "PropertyPlantAndEquipmentNet",
                "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
            ]), (ifrs_full, ["PropertyPlantAndEquipment"])],
            preferred_unit="USD",
        )
        goodwill = self._get_fact_from_taxonomies(
            [(us_gaap, ["Goodwill"]), (ifrs_full, ["Goodwill"])],
            preferred_unit="USD",
        )
        intangible_assets = self._get_fact_from_taxonomies(
            [(us_gaap, [
                "FiniteLivedIntangibleAssetsNet",
                "IntangibleAssetsNetExcludingGoodwill",
            ]), (ifrs_full, ["IntangibleAssetsOtherThanGoodwill"])],
            preferred_unit="USD",
        )
        total_assets = self._get_fact_from_taxonomies(
            [(us_gaap, ["Assets"]), (ifrs_full, ["Assets"])],
            preferred_unit="USD",
        )

        accounts_payable = self._get_fact_from_taxonomies(
            [(us_gaap, ["AccountsPayableCurrent"]),
             (ifrs_full, ["TradeAndOtherCurrentPayables"])],
            preferred_unit="USD",
        )
        short_term_debt = self._get_fact_from_taxonomies(
            [(us_gaap, [
                "ShortTermBorrowings",
                "ShortTermDebtCurrent",
                "LongTermDebtCurrent",
            ]), (ifrs_full, ["CurrentPortionOfLongtermBorrowings"])],
            preferred_unit="USD",
        )
        total_current_liabilities = self._get_fact_from_taxonomies(
            [(us_gaap, ["LiabilitiesCurrent"]), (ifrs_full, ["CurrentLiabilities"])],
            preferred_unit="USD",
        )
        long_term_debt = self._get_fact_from_taxonomies(
            [(us_gaap, [
                "LongTermDebtNoncurrent",
                "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            ]), (ifrs_full, ["LongtermBorrowings"])],
            preferred_unit="USD",
        )
        total_liabilities = self._get_fact_from_taxonomies(
            [(us_gaap, ["Liabilities"]), (ifrs_full, ["Liabilities"])],
            preferred_unit="USD",
        )
        total_equity = self._get_fact_from_taxonomies(
            [(us_gaap, [
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                "StockholdersEquity",
            ]), (ifrs_full, ["Equity"])],
            preferred_unit="USD",
        )
        retained_earnings = self._get_fact_from_taxonomies(
            [(us_gaap, ["RetainedEarningsAccumulatedDeficit"]),
             (ifrs_full, ["RetainedEarningsAccumulatedDeficit"])],
            preferred_unit="USD",
        )

        # No single balance-sheet concept is guaranteed to exist for every
        # issuer. Build the fiscal-date set from all available instant facts
        # so a valid partial balance sheet is retained instead of becoming
        # an empty statement.
        fiscal_dates = self._get_fiscal_dates_from_groups(
            cash,
            short_term_investments,
            accounts_receivable,
            inventory,
            total_current_assets,
            property_plant_equipment_net,
            goodwill,
            intangible_assets,
            total_assets,
            accounts_payable,
            short_term_debt,
            total_current_liabilities,
            long_term_debt,
            total_liabilities,
            total_equity,
            retained_earnings,
            period_type=FinancialPeriodType.INSTANT,
        )

        statements: list[BalanceSheetData] = []

        for fiscal_date in fiscal_dates:
            cash_value = self._value_on_date(cash, fiscal_date, period_type=FinancialPeriodType.INSTANT)
            sti_value = self._value_on_date(
                short_term_investments, fiscal_date,
                period_type=FinancialPeriodType.INSTANT,
            )
            std_value = self._value_on_date(
                short_term_debt, fiscal_date,
                period_type=FinancialPeriodType.INSTANT,
            )
            ltd_value = self._value_on_date(
                long_term_debt, fiscal_date,
                period_type=FinancialPeriodType.INSTANT,
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
                total_current_assets, fiscal_date,
                period_type=FinancialPeriodType.INSTANT,
            )
            current_liabilities_value = self._value_on_date(
                total_current_liabilities, fiscal_date,
                period_type=FinancialPeriodType.INSTANT,
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
                    **self._metadata_on_date_from_groups(
                        cash, short_term_investments, accounts_receivable, inventory,
                        total_current_assets, property_plant_equipment_net, goodwill,
                        intangible_assets, total_assets, accounts_payable, short_term_debt,
                        total_current_liabilities, long_term_debt, total_liabilities,
                        total_equity, retained_earnings, fiscal_date=fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    cash_and_cash_equivalents=cash_value,
                    short_term_investments=sti_value,
                    accounts_receivable=self._value_on_date(
                        accounts_receivable, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    inventory=self._value_on_date(
                        inventory, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    total_current_assets=current_assets_value,
                    property_plant_equipment_net=self._value_on_date(
                        property_plant_equipment_net, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    goodwill=self._value_on_date(
                        goodwill, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    intangible_assets=self._value_on_date(
                        intangible_assets, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    total_assets=self._value_on_date(
                        total_assets, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    accounts_payable=self._value_on_date(
                        accounts_payable, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    short_term_debt=std_value,
                    total_current_liabilities=current_liabilities_value,
                    long_term_debt=ltd_value,
                    total_liabilities=self._value_on_date(
                        total_liabilities, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    total_equity=self._value_on_date(
                        total_equity, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    retained_earnings=self._value_on_date(
                        retained_earnings, fiscal_date,
                        period_type=FinancialPeriodType.INSTANT,
                    ),
                    total_debt=total_debt,
                    net_debt=net_debt,
                    working_capital=working_capital,
                )
            )

        return statements

    @staticmethod
    def _get_fact_from_taxonomies(
        taxonomy_tags: list[tuple[dict[str, Any], list[str]]],
        preferred_unit: str,
        period_type: FinancialPeriodType | None = None,
    ) -> list[dict[str, Any]]:
        """Return the first matching fact across ordered XBRL taxonomies.

        US-GAAP remains preferred for consistency with the existing model.
        IFRS Full is a deterministic fallback for SEC filings such as Form
        20-F and Form 40-F whose primary financial statements use IFRS.
        """

        for taxonomy, tags in taxonomy_tags:
            if not isinstance(taxonomy, dict):
                continue
            facts = SECProvider._get_fact(
                taxonomy,
                tags,
                preferred_unit,
                period_type=period_type,
            )
            if facts:
                return facts
        return []

    @staticmethod
    def _get_fact(
        us_gaap: dict[str, Any],
        tags: list[str],
        preferred_unit: str,
        period_type: FinancialPeriodType | None = None,
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
                facts = units[preferred_unit]
            elif units:
                facts = next(iter(units.values()))
            else:
                facts = []

            if period_type is None:
                return facts
            filtered = [
                fact
                for fact in facts
                if SECProvider._is_fact_for_period(fact, period_type)
            ]
            if filtered:
                return filtered

        return []

    @staticmethod
    def _is_annual_fact(
        fact: dict[str, Any],
    ) -> bool:
        """Return True for annual periodic SEC financial facts."""
        annual_forms = {
            "10-K", "10-K/A", "10-KT", "10-KT/A",
            "20-F", "20-F/A", "40-F", "40-F/A",
        }
        return (
            str(fact.get("form") or "").upper() in annual_forms
            and fact.get("fp") == "FY"
        )

    @staticmethod
    def _is_quarterly_fact(
        fact: dict[str, Any],
    ) -> bool:
        """Return True only for standalone 10-Q duration facts.

        SEC's ``qtrs`` field is the primary discriminator: qtrs=1 means the
        fact represents one fiscal quarter, while qtrs=2/3 are cumulative
        year-to-date values. The filing form/fiscal period are also required.
        When a legacy CompanyFacts record omits qtrs, we accept only a
        plausible duration and the explicit Q1-Q3 fiscal-period marker; we do
        not infer quarters from calendar dates.
        """
        form = str(fact.get("form") or "").upper()
        if form not in {"10-Q", "10-Q/A"}:
            return False
        if fact.get("fp") not in {"Q1", "Q2", "Q3"}:
            return False
        if not fact.get("start") or not fact.get("end"):
            return False

        qtrs = fact.get("qtrs")
        if qtrs is not None:
            try:
                return int(qtrs) == 1
            except (TypeError, ValueError):
                return False

        try:
            duration = date.fromisoformat(str(fact["end"])) - date.fromisoformat(str(fact["start"]))
        except (TypeError, ValueError):
            return False
        return 60 <= duration.days <= 120

    @staticmethod
    def _is_instant_fact(
        fact: dict[str, Any],
    ) -> bool:
        """Return True for periodic filing instant facts used by balance sheets."""
        periodic_forms = {
            "10-K", "10-K/A", "10-KT", "10-KT/A",
            "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A",
        }
        form = str(fact.get("form") or "").upper()
        if form not in periodic_forms or not fact.get("end"):
            return False
        if fact.get("start") is not None:
            return False
        qtrs = fact.get("qtrs")
        if qtrs is not None:
            try:
                return int(qtrs) == 0
            except (TypeError, ValueError):
                return False
        return True

    @classmethod
    def _is_fact_for_period(
        cls,
        fact: dict[str, Any],
        period_type: FinancialPeriodType,
    ) -> bool:
        if period_type is FinancialPeriodType.ANNUAL:
            return cls._is_annual_fact(fact)
        if period_type is FinancialPeriodType.QUARTERLY:
            return cls._is_quarterly_fact(fact)
        if period_type is FinancialPeriodType.INSTANT:
            return cls._is_instant_fact(fact)
        raise InvalidInputError(
            f"SEC provider does not extract {period_type.value} facts directly."
        )

    @classmethod
    def _metadata_on_date_from_groups(
        cls,
        *fact_groups: list[dict[str, Any]],
        fiscal_date: date,
        period_type: FinancialPeriodType,
    ) -> dict[str, Any]:
        """Return the latest matching SEC identity for the requested period."""
        matching = []
        target = fiscal_date.isoformat()
        for facts in fact_groups:
            for fact in facts:
                if cls._is_fact_for_period(fact, period_type) and fact.get("end") == target:
                    matching.append(fact)
        if not matching:
            return {"period_type": period_type}
        latest = max(matching, key=lambda fact: fact.get("filed", ""))

        def _parse_date(value):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except (TypeError, ValueError):
                return None

        return {
            "period_start": _parse_date(latest.get("start")) if period_type is not FinancialPeriodType.INSTANT else None,
            "fiscal_year": latest.get("fy"),
            "fiscal_period": latest.get("fp"),
            "period_type": period_type,
            "filing_date": _parse_date(latest.get("filed")),
            "filing_form": latest.get("form"),
            "accession_number": latest.get("accn"),
        }

    @classmethod
    def _metadata_on_date(
        cls,
        facts: list[dict[str, Any]],
        fiscal_date: date,
        *,
        period_type: FinancialPeriodType,
    ) -> dict[str, Any]:
        matching = [
            fact
            for fact in facts
            if cls._is_fact_for_period(fact, period_type)
            and fact.get("end") == fiscal_date.isoformat()
        ]
        if not matching:
            return {"period_type": period_type}
        latest = max(matching, key=lambda fact: fact.get("filed", ""))

        def _parse_date(value):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except (TypeError, ValueError):
                return None

        return {
            "period_start": _parse_date(latest.get("start")) if period_type is not FinancialPeriodType.INSTANT else None,
            "fiscal_year": latest.get("fy"),
            "fiscal_period": latest.get("fp"),
            "period_type": period_type,
            "filing_date": _parse_date(latest.get("filed")),
            "filing_form": latest.get("form"),
            "accession_number": latest.get("accn"),
        }

    @classmethod
    def _get_fiscal_dates_from_groups(
        cls,
        *fact_groups: list[dict[str, Any]],
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
    ) -> list[date]:
        dates: set[date] = set()
        for facts in fact_groups:
            for fact in facts:
                if not cls._is_fact_for_period(fact, period_type):
                    continue
                end = fact.get("end")
                if not end:
                    continue
                try:
                    dates.add(date.fromisoformat(end))
                except (TypeError, ValueError):
                    continue
        return sorted(dates)

    @classmethod
    def _get_fiscal_dates(
        cls,
        facts: list[dict[str, Any]],
    ) -> list[date]:
        return cls._get_fiscal_dates_from_groups(facts, period_type=FinancialPeriodType.ANNUAL)

    @classmethod
    def _value_on_date(
        cls,
        facts: list[dict[str, Any]],
        fiscal_date: date,
        *,
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
    ) -> float | None:
        matching = [
            fact
            for fact in facts
            if cls._is_fact_for_period(fact, period_type)
            and fact.get("end") == fiscal_date.isoformat()
            and fact.get("val") is not None
        ]
        if not matching:
            return None
        latest = max(matching, key=lambda fact: fact.get("filed", ""))
        return float(latest["val"])

    @classmethod
    def _integer_value_on_date(
        cls,
        facts: list[dict[str, Any]],
        fiscal_date: date,
        *,
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
        annual_only: bool | None = None,
    ) -> int | None:
        # ``annual_only`` is retained as a compatibility alias for existing
        # callers/tests. New code should pass the explicit period_type.
        if annual_only is False and period_type is FinancialPeriodType.ANNUAL:
            period_type = FinancialPeriodType.INSTANT
        value = cls._value_on_date(
            facts,
            fiscal_date,
            period_type=period_type,
        )
        return int(value) if value is not None else None
