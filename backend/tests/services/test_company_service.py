from unittest.mock import Mock

import pytest

from quantcore.services.company_service import CompanyService


def make_company_data():
    data = Mock()

    data.symbol = "AAPL"
    data.name = "Apple Inc."
    data.sector = "Technology"
    data.industry = "Consumer Electronics"
    data.country = "United States"
    data.website = "https://www.apple.com"
    data.market_cap = 3_000_000_000_000

    return data


def make_existing_company():
    company = Mock()

    company.id = 1
    company.symbol = "AAPL"
    company.name = "Old Apple Name"
    company.sector = "Old Sector"
    company.industry = "Old Industry"
    company.country = "United States"
    company.website = "https://old.apple.com"
    company.market_cap = 2_000_000_000_000

    return company


def test_sync_company_creates_new_company():

    db = Mock()

    service = CompanyService.__new__(CompanyService)

    service.db = db
    service.client = Mock()
    service.repo = Mock()

    service.repo.get_by_symbol.return_value = None
    service.client.get_company_info.return_value = (
        make_company_data()
    )

    created_company = Mock()

    service.repo.create.return_value = created_company

    result = service.sync_company("AAPL")

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )

    service.repo.create.assert_called_once_with(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
    )

    assert result == created_company


def test_sync_company_returns_existing_company():


    db = Mock()

    service = CompanyService.__new__(CompanyService)

    service.db = db
    service.client = Mock()
    service.repo = Mock()

    existing_company = make_existing_company()

    service.repo.get_by_symbol.return_value = (
        existing_company
    )

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    updated_company = Mock()

    service.repo.update.return_value = updated_company

    result = service.sync_company("AAPL")

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )

    service.repo.update.assert_called_once_with(
        company=existing_company,
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
    )

    service.repo.create.assert_not_called()

    assert result == updated_company


def test_sync_company_uses_requested_symbol():

    db = Mock()

    service = CompanyService.__new__(CompanyService)

    service.db = db
    service.client = Mock()
    service.repo = Mock()

    service.repo.get_by_symbol.return_value = None
    service.client.get_company_info.return_value = (
        make_company_data()
    )

    service.repo.create.return_value = Mock()

    service.sync_company("MSFT")

    service.repo.get_by_symbol.assert_called_once_with(
        "MSFT"
    )

    service.client.get_company_info.assert_called_once_with(
        "MSFT"
    )