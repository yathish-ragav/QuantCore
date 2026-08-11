import requests
from datetime import date
from typing import Any

from quantcore.schemas.income_statement import IncomeStatementData

from .financial_provider import FinancialDataProvider


class SECProvider(FinancialDataProvider):
    """
    SEC EDGAR XBRL financial data provider.
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
        """

        if SECProvider._ticker_to_cik is not None:
            return SECProvider._ticker_to_cik

        response = requests.get(
            self.TICKER_URL,
            headers=self.HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        mapping: dict[str, str] = {}

        for company in data.values():
            ticker = company.get("ticker")
            cik = company.get("cik_str")

            if not ticker or cik is None:
                continue

            mapping[ticker.upper()] = f"{int(cik):010d}"

        SECProvider._ticker_to_cik = mapping

        return mapping

    def _get_cik(self, symbol: str) -> str:
        """
        Resolve a ticker symbol to its SEC CIK.
        """

        symbol = symbol.upper().strip()

        mapping = self._load_ticker_map()

        try:
            return mapping[symbol]
        except KeyError:
            raise ValueError(
                f"SEC CIK not found for ticker: {symbol}"
            )

    def get_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]:
        """
        Retrieve annual income statements from SEC XBRL CompanyFacts.
        """

        cik = self._get_cik(symbol)

        response = requests.get(
            f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json",
            headers=self.HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        us_gaap = data.get("facts", {}).get("us-gaap", {})

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

        fiscal_dates = self._get_fiscal_dates(revenue)

        statements = []

        for fiscal_date in fiscal_dates:
            statements.append(
                IncomeStatementData(
                    fiscal_date=fiscal_date,
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
    def _is_annual_fact(fact: dict[str, Any]) -> bool:
        """
        Determine whether an XBRL fact represents an annual 10-K result.
        """

        return (
            fact.get("form") in {"10-K", "10-K/A"}
            and fact.get("fp") == "FY"
        )

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

            dates.add(date.fromisoformat(end))

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

        matching_facts = []

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