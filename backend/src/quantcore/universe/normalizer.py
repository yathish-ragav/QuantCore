from quantcore.universe.models import UniverseCompany


def normalize_companies(
    companies: list[UniverseCompany],
) -> list[UniverseCompany]:
    normalized: dict[tuple[str, str, str], UniverseCompany] = {}

    for company in companies:
        symbol = company.symbol.strip().upper()
        cik = company.cik.strip().zfill(10)
        name = company.name.strip()
        exchange = company.exchange.strip().upper()

        if not symbol or not cik or not name or not exchange:
            continue

        if not cik.isdigit() or len(cik) != 10:
            continue

        key = (cik, symbol, exchange)
        normalized[key] = UniverseCompany(
            cik=cik,
            symbol=symbol,
            name=name,
            exchange=exchange,
        )

    return sorted(
        normalized.values(),
        key=lambda company: (company.symbol, company.exchange, company.cik),
    )
