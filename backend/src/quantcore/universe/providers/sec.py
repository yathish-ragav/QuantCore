import requests

from quantcore.universe.models import UniverseCompany


class SECUniverseProvider:
    """
    Loads the SEC's ticker / CIK / exchange company universe.
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

        data = response.json()

        companies = []

        for item in data.values():

            cik = item.get("cik")
            symbol = item.get("ticker")
            name = item.get("name")
            exchange = item.get("exchange")

            if cik is None:
                continue

            if not symbol:
                continue

            if not name:
                continue

            companies.append(
                UniverseCompany(
                    cik=f"{int(cik):010d}",
                    symbol=symbol.upper().strip(),
                    name=name.strip(),
                    exchange=(
                        exchange.strip()
                        if exchange
                        else ""
                    ),
                )
            )

        return companies