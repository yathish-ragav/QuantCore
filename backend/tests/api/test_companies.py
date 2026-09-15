from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_company():
    company = Mock()

    company.id = 1
    company.name = "Apple Inc."
    company.sector = "Technology"
    company.industry = "Consumer Electronics"
    company.country = "United States"
    company.website = "https://www.apple.com"
    company.market_cap = 3000000000000

    return company


def test_get_company_returns_company_data():

    company = make_company()

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.get_company.return_value = company

        mock_service.return_value = service

        response = client.get(
            "/companies/AAPL"
        )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "id": 1,
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://www.apple.com",
        "market_cap": 3000000000000,
    }

    service.get_company.assert_called_once_with(
        "AAPL"
    )

    service.sync_company.assert_not_called()


def test_get_company_normalizes_lowercase_symbol():

    company = make_company()

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.get_company.return_value = company

        mock_service.return_value = service

        response = client.get(
            "/companies/aapl"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["symbol"] == "AAPL"

    service.get_company.assert_called_once_with(
        "AAPL"
    )

    service.sync_company.assert_not_called()


def test_get_company_normalizes_mixed_case_symbol():

    company = make_company()

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.get_company.return_value = company

        mock_service.return_value = service

        response = client.get(
            "/companies/aApL"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["symbol"] == "AAPL"

    service.get_company.assert_called_once_with(
        "AAPL"
    )

    service.sync_company.assert_not_called()


def test_get_company_propagates_service_error():

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.get_company.side_effect = ValueError(
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

        service.get_company.assert_called_once_with(
            "AAPL"
        )

        service.sync_company.assert_not_called()


def test_sync_company_returns_company_data():

    company = make_company()

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.sync_company.return_value = company

        mock_service.return_value = service

        response = client.post(
            "/companies/AAPL/sync"
        )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "id": 1,
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://www.apple.com",
        "market_cap": 3000000000000,
    }

    service.sync_company.assert_called_once_with(
        "AAPL"
    )

    service.get_company.assert_not_called()


def test_sync_company_normalizes_lowercase_symbol():

    company = make_company()

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.sync_company.return_value = company

        mock_service.return_value = service

        response = client.post(
            "/companies/aapl/sync"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["symbol"] == "AAPL"

    service.sync_company.assert_called_once_with(
        "AAPL"
    )

    service.get_company.assert_not_called()


def test_sync_company_normalizes_mixed_case_symbol():

    company = make_company()

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.sync_company.return_value = company

        mock_service.return_value = service

        response = client.post(
            "/companies/aApL/sync"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["symbol"] == "AAPL"

    service.sync_company.assert_called_once_with(
        "AAPL"
    )

    service.get_company.assert_not_called()


def test_sync_company_propagates_service_error():

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:

        service = Mock()

        service.sync_company.side_effect = ValueError(
            "Company not found"
        )

        mock_service.return_value = service

        with pytest.raises(
            ValueError,
            match="Company not found",
        ):
            client.post(
                "/companies/AAPL/sync"
            )

        service.sync_company.assert_called_once_with(
            "AAPL"
        )

        service.get_company.assert_not_called()

def test_search_companies_returns_listing_identity():
    company = make_company()
    company.cik = "0000320193"

    security = Mock()
    security.id = 10
    security.company_id = company.id
    security.symbol = "AAPL"
    security.exchange = "NASDAQ"
    security.status.value = "ACTIVE"
    security.company = company

    with patch(
        "quantcore.api.dependencies.CompanyService"
    ) as mock_service:
        service = Mock()
        service.search.return_value = [security]
        mock_service.return_value = service

        response = client.get("/companies/search?q=apple&limit=10")

    assert response.status_code == 200
    assert response.json() == [
        {
            "security_id": 10,
            "company_id": 1,
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "name": "Apple Inc.",
            "cik": "0000320193",
            "status": "ACTIVE",
        }
    ]
    service.search.assert_called_once_with("apple", limit=10)


def test_search_companies_rejects_empty_query():
    response = client.get("/companies/search?q=")

    assert response.status_code == 422
