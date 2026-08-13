from quantcore.universe.models import UniverseCompany
from quantcore.universe.normalizer import normalize_companies


def test_normalize_companies_preserves_multiple_securities_for_same_cik():

    companies = [
        UniverseCompany(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
        UniverseCompany(
            cik="0000320193",
            symbol="AAPL-A",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
    ]

    result = normalize_companies(companies)

    assert len(result) == 2

    assert {
        company.symbol
        for company in result
    } == {"AAPL", "AAPL-A"}

    assert all(
        company.cik == "0000320193"
        for company in result
    )