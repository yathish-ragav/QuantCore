from quantcore.universe.models import UniverseCompany


DEFAULT_US_EXCHANGES = {
    "NASDAQ",
    "NYSE",
    "NYSE MKT",
    "NYSE AMERICAN",
    "NYSE ARCA",
}


def filter_us_equities(
    companies: list[UniverseCompany],
) -> list[UniverseCompany]:

    return [
        company
        for company in companies
        if company.exchange.upper()
        in DEFAULT_US_EXCHANGES
    ]