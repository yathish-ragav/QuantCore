import requests

from quantcore.core.exceptions import DataValidationError, ExternalDataError
from quantcore.universe.models import UniverseCompany


class SECUniverseProvider:
    """Load the SEC ticker / CIK / exchange company universe."""

    URL = (
        "https://www.sec.gov/files/"
        "company_tickers_exchange.json"
    )

    HEADERS = {
        "User-Agent": (
            "QuantCore/1.0 "
            "contact: yathishragav@gmail.com"
        ),
        "Accept-Encoding": "gzip, deflate",
    }

    def fetch(self) -> list[UniverseCompany]:
        try:
            response = requests.get(
                self.URL,
                headers=self.HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ExternalDataError(
                "Failed to retrieve SEC company universe."
            ) from exc
        except ValueError as exc:
            raise DataValidationError(
                "SEC company universe response was not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise DataValidationError(
                "SEC company universe response must be an object."
            )

        fields = payload.get("fields")
        rows = payload.get("data")

        expected_fields = [
            "cik",
            "name",
            "ticker",
            "exchange",
        ]

        if fields != expected_fields:
            raise DataValidationError(
                "Unexpected SEC universe schema."
            )

        if not isinstance(rows, list):
            raise DataValidationError(
                "SEC universe data is not a list."
            )

        companies: list[UniverseCompany] = []

        try:
            for row in rows:
                if not isinstance(row, list):
                    continue

                if len(row) != len(fields):
                    continue

                cik, name, ticker, exchange = row

                if cik is None or not ticker or not name:
                    continue

                companies.append(
                    UniverseCompany(
                        cik=f"{int(cik):010d}",
                        symbol=str(ticker).strip().upper(),
                        name=str(name).strip(),
                        exchange=(
                            str(exchange).strip()
                            if exchange
                            else ""
                        ),
                    )
                )
        except (TypeError, ValueError) as exc:
            raise DataValidationError(
                "Invalid SEC universe record."
            ) from exc

        return companies
