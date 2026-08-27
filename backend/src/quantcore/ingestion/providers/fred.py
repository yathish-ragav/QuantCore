from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import requests

from quantcore.core.config import settings
from quantcore.core.exceptions import DataValidationError, ExternalDataError, InvalidInputError
from quantcore.schemas.macro import MacroObservationData, MacroSeriesData

from .macro_provider import MacroDataProvider


class FREDClient(MacroDataProvider):
    """FRED/ALFRED economic-data provider."""

    SOURCE = "FRED"
    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self) -> None:
        if not settings.FRED_API_KEY:
            raise InvalidInputError("FRED_API_KEY must be configured for macro data ingestion.")
        self.api_key = settings.FRED_API_KEY

    def _get(self, path: str, params: dict) -> dict:
        request_params = {
            **params,
            "api_key": self.api_key,
            "file_type": "json",
        }
        try:
            response = requests.get(
                f"{self.BASE_URL}/{path}",
                params=request_params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ExternalDataError("Failed to retrieve macro data from FRED.") from exc
        except ValueError as exc:
            raise DataValidationError("FRED returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise DataValidationError("FRED response must be an object.")
        return payload

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        return date.fromisoformat(value)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    def get_series(self, series_id: str) -> MacroSeriesData:
        series_id = series_id.strip().upper()
        if not series_id:
            raise InvalidInputError("Series ID must not be empty.")

        payload = self._get("series", {"series_id": series_id})
        rows = payload.get("seriess")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise DataValidationError(f"FRED did not return exactly one series for '{series_id}'.")

        item = rows[0]
        try:
            return MacroSeriesData(
                series_id=item["id"],
                title=item["title"],
                frequency=item["frequency"],
                frequency_short=item.get("frequency_short"),
                units=item["units"],
                units_short=item.get("units_short"),
                seasonal_adjustment=item.get("seasonal_adjustment"),
                seasonal_adjustment_short=item.get("seasonal_adjustment_short"),
                observation_start=self._parse_date(item.get("observation_start")),
                observation_end=self._parse_date(item.get("observation_end")),
                last_updated=self._parse_datetime(item.get("last_updated")),
                notes=item.get("notes"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataValidationError(f"Invalid FRED series metadata for '{series_id}'.") from exc

    def get_observations(
        self,
        series_id: str,
        *,
        vintage_date: date | None = None,
    ) -> list[MacroObservationData]:
        series_id = series_id.strip().upper()
        if not series_id:
            raise InvalidInputError("Series ID must not be empty.")

        params = {
            "series_id": series_id,
            "sort_order": "asc",
        }
        requested_vintage = vintage_date or date.today()
        if requested_vintage > date.today():
            raise InvalidInputError("Vintage date must not be in the future.")
        params["realtime_start"] = requested_vintage.isoformat()
        params["realtime_end"] = requested_vintage.isoformat()

        payload = self._get("series/observations", params)
        rows = payload.get("observations")
        if not isinstance(rows, list):
            raise DataValidationError(f"FRED observations for '{series_id}' must be a list.")

        observations: list[MacroObservationData] = []

        for item in rows:
            if not isinstance(item, dict):
                raise DataValidationError(f"Invalid FRED observation for '{series_id}'.")
            try:
                raw_value = item.get("value")
                value = None if raw_value in (None, ".", "") else Decimal(str(raw_value))
                row_realtime_start = self._parse_date(item.get("realtime_start"))
                row_realtime_end = self._parse_date(item.get("realtime_end"))
                if row_realtime_start is None or row_realtime_end is None:
                    raise DataValidationError(
                        f"FRED observation for '{series_id}' is missing realtime-period metadata."
                    )
                if not row_realtime_start <= requested_vintage <= row_realtime_end:
                    raise DataValidationError(
                        f"FRED observation for '{series_id}' does not cover requested "
                        f"vintage {requested_vintage.isoformat()}."
                    )
                observations.append(
                    MacroObservationData(
                        series_id=series_id,
                        observation_date=date.fromisoformat(item["date"]),
                        value=value,
                        realtime_start=row_realtime_start,
                        realtime_end=row_realtime_end,
                        vintage_date=requested_vintage,
                    )
                )
            except DataValidationError:
                raise
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise DataValidationError(f"Invalid FRED observation for '{series_id}'.") from exc

        return observations
