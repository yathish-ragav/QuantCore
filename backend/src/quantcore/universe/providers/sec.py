import requests

from quantcore.universe.models import UniverseCompany


class SECUniverseProvider:
    """
    Loads the SEC ticker / CIK / exchange company universe.
    """

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
        response = requests.get(
            self.URL,
            headers=self.HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        fields = payload.get("fields")
        rows = payload.get("data")

        if fields != [
            "cik",
            "name",
            "ticker",
            "exchange",
        ]:
            raise ValueError(
                "Unexpected SEC universe schema."
            )

        if not isinstance(rows, list):
            raise ValueError(
                "SEC universe data is not a list."
            )

        companies = []

        for row in rows:

            if not isinstance(row, list):
                continue

            if len(row) != len(fields):
                continue

            cik, name, ticker, exchange = row

            if cik is None:
                continue

            if not ticker:
                continue

            if not name:
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

        return companies