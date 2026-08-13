from quantcore.universe.filters import filter_us_equities
from quantcore.universe.models import UniverseCompany


def make_company(
    symbol: str,
    exchange: str,
) -> UniverseCompany:

    return UniverseCompany(
        cik="0000000001",
        symbol=symbol,
        name=f"{symbol} Company",
        exchange=exchange,
    )


def test_filter_us_equities_keeps_major_exchanges():

    companies = [
        make_company("AAPL", "NASDAQ"),
        make_company("IBM", "NYSE"),
        make_company("XYZ", "NYSE MKT"),
    ]

    result = filter_us_equities(companies)

    assert [
        company.symbol
        for company in result
    ] == [
        "AAPL",
        "IBM",
        "XYZ",
    ]


def test_filter_us_equities_removes_unsupported_exchange():

    companies = [
        make_company("AAPL", "NASDAQ"),
        make_company("ABC", "OTC"),
    ]

    result = filter_us_equities(companies)

    assert [
        company.symbol
        for company in result
    ] == ["AAPL"]


def test_filter_us_equities_is_case_insensitive():

    companies = [
        make_company("AAPL", "nasdaq"),
    ]

    result = filter_us_equities(companies)

    assert len(result) == 1
    assert result[0].symbol == "AAPL"