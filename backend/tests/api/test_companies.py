from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_company():
    company = Mock()

    company.id = 1
    company.symbol = "AAPL"
    company.name = "Apple Inc."
    company.sector = "Technology"
    company.industry = "Consumer Electronics"
    company.country = "United States"
    company.website = "https://www.apple.com"
    company.market_cap = 3_000_000_000_000

    return company


@patch(
    "quantcore.api.endpoints.companies.CompanyService"
)
def test_get_company_returns_company_data(
    mock_service,
):
    company = make_company()

    service = Mock()
    service.sync_company.return_value = company

    mock_service.return_value = service

    response = client.get(
        "/companies/AAPL"
    )

    assert response.status_code == 200

    assert response.json() == {
        "id": 1,
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://www.apple.com",
        "market_cap": 3_000_000_000_000,
    }

    service.sync_company.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.endpoints.companies.CompanyService"
)
def test_get_company_normalizes_lowercase_symbol(
    mock_service,
):
    company = make_company()

    service = Mock()
    service.sync_company.return_value = company

    mock_service.return_value = service

    response = client.get(
        "/companies/aapl"
    )

    assert response.status_code == 200

    service.sync_company.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.endpoints.companies.CompanyService"
)
def test_get_company_normalizes_mixed_case_symbol(
    mock_service,
):
    company = make_company()

    service = Mock()
    service.sync_company.return_value = company

    mock_service.return_value = service

    response = client.get(
        "/companies/aApL"
    )

    assert response.status_code == 200

    service.sync_company.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.endpoints.companies.CompanyService"
)
def test_get_company_propagates_service_error(
    mock_service,
):
    service = Mock()

    service.sync_company.side_effect = ValueError(
        "Company not found"
    )

    mock_service.return_value = service

    with pytest.raises(
        ValueError,
        match="Company not found",
    ):
        client.get(
            "/companies/AAPL"
        )

    service.sync_company.assert_called_once_with(
        "AAPL"
    )