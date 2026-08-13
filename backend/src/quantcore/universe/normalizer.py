from quantcore.universe.models import UniverseCompany


def normalize_companies(
    companies: list[UniverseCompany],
) -> list[UniverseCompany]:

    normalized: dict[str, UniverseCompany] = {}

    for company in companies:

        symbol = company.symbol.strip().upper()

        cik = company.cik.strip()

        name = company.name.strip()

        exchange = company.exchange.strip().upper()

        if not symbol:
            continue

        if not cik:
            continue

        if not name:
            continue

        normalized[symbol] = UniverseCompany(
            cik=cik,
            symbol=symbol,
            name=name,
            exchange=exchange,
        )

    return sorted(
        normalized.values(),
        key=lambda company: company.symbol,
    )