from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from urllib.parse import parse_qs, urlparse

import requests

from quantcore.core.config import settings
from quantcore.core.enums import SecurityType
from quantcore.core.exceptions import ConfigurationError, DataValidationError, ExternalDataError
from quantcore.universe.models import UniverseSecurityClassification


class MassiveUniverseProvider:
    """Bulk Massive reference-data classifier for the managed security universe.

    Massive is used only to establish instrument classification here. SEC remains
    authoritative for issuer identity and the current listing universe.
    """

    SOURCE = "MASSIVE"
    URL = "https://api.massive.com/v3/reference/tickers"

    # Massive's documented U.S. stock ticker-type codes are normalized into
    # QuantCore's smaller canonical instrument taxonomy. Codes that do not have
    # a safe one-to-one mapping remain OTHER rather than being guessed.
    _TYPE_MAP = {
        "CS": SecurityType.COMMON_STOCK,
        "OS": SecurityType.COMMON_STOCK,
        "P": SecurityType.PREFERRED_STOCK,
        "PFD": SecurityType.PREFERRED_STOCK,
        "ETF": SecurityType.ETF,
        "ETS": SecurityType.ETF,
        "ETV": SecurityType.OTHER,
        "ADR": SecurityType.ADR,
        "ADRC": SecurityType.ADR,
        "ADRP": SecurityType.ADR,
        "ADRR": SecurityType.ADR,
        "ADRW": SecurityType.ADR,
        "WARRANT": SecurityType.WARRANT,
        "WARRANTS": SecurityType.WARRANT,
        "UNIT": SecurityType.UNIT,
        "RIGHT": SecurityType.RIGHT,
        "SPAC": SecurityType.SPAC,
        "FUND": SecurityType.OTHER,
        "SP": SecurityType.OTHER,
        "ETN": SecurityType.OTHER,
        "GDR": SecurityType.OTHER,
        "OTHER": SecurityType.OTHER,
        "NYRS": SecurityType.OTHER,
        "AGEN": SecurityType.OTHER,
        "EQLK": SecurityType.OTHER,
        "BOND": SecurityType.OTHER,
        "BASKET": SecurityType.OTHER,
        "LT": SecurityType.OTHER,
    }

    _MAX_429_RETRIES = 5
    _MAX_BACKOFF_SECONDS = 60.0

    def __init__(
        self,
        api_key: str | None = None,
        *,
        sleep_fn=time.sleep,
        request_interval_seconds: float | None = None,
        monotonic_fn=time.monotonic,
    ) -> None:
        self.api_key = (
            api_key if api_key is not None else settings.MASSIVE_API_KEY
        ).strip()
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._request_interval_seconds = (
            settings.MASSIVE_REFERENCE_REQUEST_INTERVAL_SECONDS
            if request_interval_seconds is None
            else request_interval_seconds
        )
        if self._request_interval_seconds < 0:
            raise ConfigurationError(
                "MASSIVE_REFERENCE_REQUEST_INTERVAL_SECONDS cannot be negative."
            )
        self._last_request_started_at: float | None = None
        if not self.api_key:
            raise ConfigurationError(
                "MASSIVE_API_KEY is required for security classification."
            )

    @classmethod
    def _security_type(cls, provider_type: object) -> SecurityType:
        normalized = str(provider_type or "").strip().upper()
        return cls._TYPE_MAP.get(normalized, SecurityType.UNKNOWN)

    def _wait_for_request_slot(self) -> None:
        if self._last_request_started_at is None or self._request_interval_seconds <= 0:
            return

        elapsed = self._monotonic() - self._last_request_started_at
        remaining = self._request_interval_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)

    def _mark_request_started(self) -> None:
        self._last_request_started_at = self._monotonic()

    def _get(self, url: str, *, params: dict[str, object] | None = None) -> dict:
        query = dict(params or {})
        parsed = urlparse(url)
        if "apiKey" not in parse_qs(parsed.query):
            query["apiKey"] = self.api_key

        for attempt in range(self._MAX_429_RETRIES + 1):
            self._wait_for_request_slot()
            self._mark_request_started()
            try:
                response = requests.get(url, params=query, timeout=30)
            except requests.RequestException as exc:
                raise ExternalDataError(
                    "Massive security-classification request failed."
                ) from exc

            if response.status_code == 429:
                if attempt >= self._MAX_429_RETRIES:
                    try:
                        response.raise_for_status()
                    except requests.RequestException as exc:
                        raise ExternalDataError(
                            "Massive security-classification request failed after rate-limit retries."
                        ) from exc
                    raise ExternalDataError(
                        "Massive security-classification request failed after rate-limit retries."
                    )

                retry_after = None
                try:
                    retry_after = float(response.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    pass

                delay = (
                    max(retry_after, 0.0)
                    if retry_after is not None
                    else min(2**attempt, self._MAX_BACKOFF_SECONDS)
                )
                self._sleep(min(delay, self._MAX_BACKOFF_SECONDS))
                continue

            try:
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                raise ExternalDataError(
                    "Massive security-classification request failed."
                ) from exc
            except ValueError as exc:
                raise DataValidationError(
                    "Massive security-classification response was not valid JSON."
                ) from exc
            break
        else:
            raise ExternalDataError(
                "Massive security-classification request failed after rate-limit retries."
            )

        if not isinstance(payload, dict):
            raise DataValidationError(
                "Massive security-classification response must be an object."
            )

        status = payload.get("status")
        if status not in (None, "OK"):
            raise ExternalDataError(
                f"Massive returned status {status!r} for security classification."
            )
        return payload

    def fetch(self) -> list[UniverseSecurityClassification]:
        """Fetch all currently active stock reference rows in bulk."""
        output: list[UniverseSecurityClassification] = []
        url = self.URL
        params: dict[str, object] | None = {
            "market": "stocks",
            "active": "true",
            "order": "asc",
            "sort": "ticker",
            "limit": 1000,
        }
        observed_at = datetime.now(timezone.utc)

        while url:
            payload = self._get(url, params=params)
            params = None

            rows = payload.get("results", [])
            if not isinstance(rows, list):
                raise DataValidationError(
                    "Massive security-classification results must be a list."
                )

            for row in rows:
                if not isinstance(row, dict):
                    continue

                cik = str(row.get("cik") or "").strip()
                symbol = str(row.get("ticker") or "").strip().upper()
                if not cik or not symbol:
                    continue

                try:
                    normalized_cik = f"{int(cik):010d}"
                except (TypeError, ValueError):
                    continue

                provider_type = str(row.get("type") or "").strip().upper() or None
                output.append(
                    UniverseSecurityClassification(
                        cik=normalized_cik,
                        symbol=symbol,
                        security_type=self._security_type(provider_type),
                        source=self.SOURCE,
                        observed_at=observed_at,
                        source_reference=(
                            f"MASSIVE:TICKER:{symbol}:{normalized_cik}"
                        ),
                        provider_type=provider_type,
                    )
                )

            next_url = payload.get("next_url")
            url = str(next_url) if next_url else ""

        return output
