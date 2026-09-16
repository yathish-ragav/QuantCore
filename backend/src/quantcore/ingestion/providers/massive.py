from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests

from quantcore.core.config import settings
from quantcore.core.enums import CorporateActionType, PriceBasis, SecurityType
from quantcore.core.exceptions import (
    ConfigurationError,
    DataValidationError,
    ExternalDataError,
    InvalidInputError,
    RateLimitError,
)
from quantcore.schemas.company import CompanyData
from quantcore.schemas.corporate_action import CorporateActionData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData
from quantcore.schemas.quote import QuoteData

from .base import MarketDataProvider
from .quote_provider import QuoteProvider


class MassiveClient(MarketDataProvider, QuoteProvider):
    """Production-oriented U.S. equity data adapter for Massive."""

    SOURCE = "MASSIVE"
    BASE_URL = "https://api.massive.com"

    _PERIOD_DAYS = {
        "1d": 2,
        "5d": 7,
        "1mo": 35,
        "3mo": 100,
        "6mo": 190,
        "1y": 370,
        "2y": 740,
        "5y": 1850,
        "10y": 3700,
    }

    def __init__(self) -> None:
        self.api_key = settings.MASSIVE_API_KEY.strip()
        if not self.api_key:
            raise ConfigurationError(
                "MASSIVE_API_KEY is required for the Massive provider."
            )

    def _get(
        self,
        path_or_url: str,
        *,
        params: dict | None = None,
        accepted_statuses: tuple[str, ...] = ("OK",),
    ) -> dict:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else f"{self.BASE_URL}{path_or_url}"
        )
        query = dict(params or {})
        parsed = urlparse(url)
        existing = parse_qs(parsed.query)
        if "apiKey" not in existing:
            query["apiKey"] = self.api_key
        try:
            response = requests.get(
                url,
                params=query,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ExternalDataError(
                "Massive market-data request failed before a response was received."
            ) from exc

        if response.status_code == 429:
            retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
            raise RateLimitError(
                "Massive rate limit exceeded (HTTP 429).",
                retry_after_seconds=retry_after,
            )

        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ExternalDataError(
                f"Massive market-data request failed with HTTP {response.status_code}."
            ) from exc
        except ValueError as exc:
            raise DataValidationError(
                "Massive response was not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise DataValidationError("Massive response must be an object.")

        status = payload.get("status")
        if status is not None and status not in accepted_statuses:
            raise ExternalDataError(
                f"Massive returned status {status!r}."
            )
        return payload

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float:
        """Parse a provider Retry-After value without trusting malformed input."""
        if value is None:
            return 60.0
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 60.0

    @staticmethod
    def _period_start(period: str) -> date:
        normalized = period.strip().lower()
        if normalized == "max":
            return date(2003, 1, 1)
        if normalized not in MassiveClient._PERIOD_DAYS:
            raise InvalidInputError(
                "Unsupported Massive price period. Use one of "
                "1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, or max."
            )
        return date.today() - timedelta(
            days=MassiveClient._PERIOD_DAYS[normalized]
        )

    def _paged_results(
        self,
        path: str,
        *,
        params: dict,
        accepted_statuses: tuple[str, ...] = ("OK",),
    ) -> list[dict]:
        payload = self._get(
            path,
            params=params,
            accepted_statuses=accepted_statuses,
        )
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise DataValidationError("Massive results must be a list.")

        output = [item for item in results if isinstance(item, dict)]
        next_url = payload.get("next_url")
        while next_url:
            payload = self._get(
                str(next_url),
                accepted_statuses=accepted_statuses,
            )
            page = payload.get("results", [])
            if not isinstance(page, list):
                raise DataValidationError("Massive paginated results must be a list.")
            output.extend(item for item in page if isinstance(item, dict))
            next_url = payload.get("next_url")
        return output

    def get_company_info(self, symbol: str) -> CompanyData:
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        payload = self._get(f"/v3/reference/tickers/{symbol}")
        item = payload.get("results")
        if not isinstance(item, dict):
            raise DataValidationError(
                "Massive ticker response is missing results."
            )

        returned = str(item.get("ticker") or symbol).upper()
        if returned != symbol:
            raise DataValidationError(
                f"Massive returned ticker {returned!r} for {symbol!r}."
            )

        address = item.get("address") or {}
        address_country = address.get("country")
        locale = str(item.get("locale") or "").strip().lower()
        locale_country = {
            "us": "United States",
            "global": None,
        }.get(locale)

        # Massive exposes SIC classification, not a separate industry taxonomy.
        industry = item.get("sic_description")
        country = address_country or locale_country
        website = item.get("homepage_url")

        market_cap = item.get("market_cap")
        try:
            market_cap = int(market_cap) if market_cap is not None else None
        except (TypeError, ValueError):
            market_cap = None

        provider_type = str(item.get("type") or "").strip().upper()
        security_type = {
            "CS": SecurityType.COMMON_STOCK,
            "COMMON STOCK": SecurityType.COMMON_STOCK,
            "P": SecurityType.PREFERRED_STOCK,
            "PREFERRED": SecurityType.PREFERRED_STOCK,
            "ETF": SecurityType.ETF,
            "ADR": SecurityType.ADR,
            "ADRC": SecurityType.ADR,
            "WARRANT": SecurityType.WARRANT,
            "WARRANTS": SecurityType.WARRANT,
            "UNIT": SecurityType.UNIT,
            "RIGHT": SecurityType.RIGHT,
            "SPAC": SecurityType.SPAC,
        }.get(provider_type, SecurityType.UNKNOWN)

        return CompanyData(
            symbol=symbol,
            name=str(item.get("name") or ""),
            # Massive documents SIC classification, not a separate sector
            # taxonomy. Do not fabricate a sector from SIC description.
            sector=None,
            industry=(str(industry) if industry is not None else None),
            country=(str(country) if country else None),
            website=(str(website) if website else None),
            market_cap=market_cap,
            security_type=security_type,
        )

    def get_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> list[PriceData]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        start = self._period_start(period)
        end = date.today()

        aggregate_statuses = ("OK", "DELAYED")
        raw = self._paged_results(
            f"/v2/aggs/ticker/{symbol}/range/1/day/{start.isoformat()}/{end.isoformat()}",
            params={"adjusted": "false", "sort": "asc", "limit": 50000},
            accepted_statuses=aggregate_statuses,
        )
        adjusted = self._paged_results(
            f"/v2/aggs/ticker/{symbol}/range/1/day/{start.isoformat()}/{end.isoformat()}",
            params={"adjusted": "true", "sort": "asc", "limit": 50000},
            accepted_statuses=aggregate_statuses,
        )

        adjusted_by_timestamp = {
            int(row["t"]): row
            for row in adjusted
            if "t" in row and "c" in row
        }

        prices: list[PriceData] = []
        for row in raw:
            try:
                timestamp_ms = int(row["t"])
                adjusted_row = adjusted_by_timestamp.get(timestamp_ms)
                timestamp = datetime.fromtimestamp(
                    timestamp_ms / 1000,
                    tz=timezone.utc,
                )
                prices.append(
                    PriceData(
                        date=timestamp,
                        open=float(row["o"]),
                        high=float(row["h"]),
                        low=float(row["l"]),
                        close=float(row["c"]),
                        adjusted_close=(
                            float(adjusted_row["c"])
                            if adjusted_row is not None
                            else None
                        ),
                        price_basis=PriceBasis.UNADJUSTED,
                        volume=int(row.get("v", 0)),
                        dividends=0.0,
                        stock_splits=0.0,
                    )
                )
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise DataValidationError(
                    "Invalid Massive aggregate row."
                ) from exc

        return prices

    def get_corporate_actions(
        self,
        symbol: str,
        period: str = "max",
    ) -> list[CorporateActionData]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")
        start = self._period_start(period)
        end = date.today()

        dividends = self._paged_results(
            "/stocks/v1/dividends",
            params={
                "ticker": symbol,
                "ex_dividend_date.gte": start.isoformat(),
                "ex_dividend_date.lte": end.isoformat(),
                "sort": "ex_dividend_date.asc",
                "limit": 5000,
            },
        )
        splits = self._paged_results(
            "/stocks/v1/splits",
            params={
                "ticker": symbol,
                "execution_date.gte": start.isoformat(),
                "execution_date.lte": end.isoformat(),
                "sort": "execution_date.asc",
                "limit": 5000,
            },
        )

        actions: list[CorporateActionData] = []
        for item in dividends:
            try:
                effective = date.fromisoformat(str(item["ex_dividend_date"]))
                amount = item.get("cash_amount")
                actions.append(
                    CorporateActionData(
                        effective_date=effective,
                        action_type=CorporateActionType.DIVIDEND,
                        amount=float(amount) if amount is not None else None,
                        source_reference=(
                            f"MASSIVE:DIVIDEND:{str(item['id'])}"
                            if item.get("id") is not None
                            else None
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid Massive dividend row."
                ) from exc

        for item in splits:
            try:
                effective = date.fromisoformat(str(item["execution_date"]))
                split_from = float(item["split_from"])
                split_to = float(item["split_to"])
                if split_from <= 0 or split_to <= 0:
                    raise ValueError("split ratio components must be positive")
                actions.append(
                    CorporateActionData(
                        effective_date=effective,
                        action_type=CorporateActionType.STOCK_SPLIT,
                        split_ratio=split_to / split_from,
                        source_reference=(
                            f"MASSIVE:STOCK_SPLIT:{str(item['id'])}"
                            if item.get("id") is not None
                            else None
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid Massive split row."
                ) from exc

        return sorted(
            actions,
            key=lambda item: (
                item.effective_date,
                item.action_type.value,
            ),
        )

    def get_news(self, symbol: str) -> list[NewsData]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        articles = self._paged_results(
            "/v2/reference/news",
            params={
                "ticker": symbol,
                "order": "desc",
                "sort": "published_utc",
                "limit": 1000,
            },
        )
        output: list[NewsData] = []
        for item in articles:
            try:
                publisher = item.get("publisher") or {}
                published_at = item.get("published_utc")
                parsed = (
                    datetime.fromisoformat(
                        str(published_at).replace("Z", "+00:00")
                    )
                    if published_at
                    else None
                )
                output.append(
                    NewsData(
                        title=str(item.get("title") or ""),
                        publisher=str(
                            publisher.get("name")
                            or publisher.get("homepage_url")
                            or ""
                        ),
                        summary=str(item.get("description") or ""),
                        url=str(item["article_url"]),
                        published_at=parsed,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid Massive news row."
                ) from exc
        return output

    def get_quote(self, symbol: str) -> QuoteData:
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        payload = self._get(
            f"/v3/snapshot",
            params={"ticker.any_of": symbol},
        )
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise DataValidationError("Massive snapshot returned no quote.")

        item = results[0]
        returned_symbol = str(item.get("ticker") or "").strip().upper()
        if returned_symbol != symbol:
            raise DataValidationError(
                f"Massive returned ticker {returned_symbol!r} for {symbol!r}."
            )
        session = item.get("session") or {}
        timestamp_ns = session.get("last_updated") or item.get("last_updated")
        if timestamp_ns is None:
            timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.fromtimestamp(
                int(timestamp_ns) / 1_000_000_000,
                tz=timezone.utc,
            )

        price = session.get("price")
        if price is None:
            price = session.get("close")
        previous_close = session.get("previous_close")
        change = (
            float(price) - float(previous_close)
            if price is not None and previous_close is not None
            else 0.0
        )
        change_percent = (
            (change / float(previous_close)) * 100
            if previous_close not in (None, 0)
            else 0.0
        )

        return QuoteData(
            symbol=symbol,
            name=str(item.get("name") or ""),
            price=float(price or 0.0),
            change=change,
            change_percent=change_percent,
            day_low=session.get("low"),
            day_high=session.get("high"),
            volume=session.get("volume"),
            previous_close=previous_close,
            open=session.get("open"),
            timestamp=timestamp,
            source=self.SOURCE,
        )
