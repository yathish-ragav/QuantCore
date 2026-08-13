from quantcore.universe.models import UniverseCompany
from quantcore.universe.normalizer import normalize_companies


def test_normalize_companies():

    companies = [
        UniverseCompany(
            cik="0000320193",
            symbol=" aapl ",
            name=" Apple Inc. ",
            exchange=" nasdaq ",
        ),
    ]

    result = normalize_companies(companies)

    assert len(result) == 1

    assert result[0].cik == "0000320193"
    assert result[0].symbol == "AAPL"
    assert result[0].name == "Apple Inc."
    assert result[0].exchange == "NASDAQ"


def test_normalize_companies_deduplicates_symbols():

    companies = [
        UniverseCompany(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
        UniverseCompany(
            cik="0000320193",
            symbol="aapl",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
    ]

    result = normalize_companies(companies)

    assert len(result) == 1


def test_normalize_companies_sorts_by_symbol():

    companies = [
        UniverseCompany(
            cik="0000789019",
            symbol="MSFT",
            name="Microsoft Corporation",
            exchange="NASDAQ",
        ),
        UniverseCompany(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
    ]

    result = normalize_companies(companies)

    assert [
        company.symbol
        for company in result
    ] == ["AAPL", "MSFT"]