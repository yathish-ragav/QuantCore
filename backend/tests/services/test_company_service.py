from unittest.mock import Mock

import pytest

from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.schemas.company import CompanyData
from quantcore.services.company_service import CompanyService


def make_company_data(
    symbol="AAPL",
    name="Apple Inc.",
    sector="Technology",
    industry="Consumer Electronics",
    country="United States",
    website="https://www.apple.com",
    market_cap=3_000_000_000_000,
):
    return CompanyData(
        symbol=symbol,
        name=name,
        sector=sector,
        industry=industry,
        country=country,
        website=website,
        market_cap=market_cap,
    )


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


def make_service():
    db = Mock()

    service = CompanyService.__new__(
        CompanyService
    )

    service.db = db
    service.client = Mock()
    service.repo = Mock()

    return service, db


def test_sync_company_creates_new_company():

    service, db = make_service()

    service.repo.get_by_symbol.return_value = None

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    created_company = Mock()

    service.repo.create.return_value = (
        created_company
    )

    result = service.sync_company("AAPL")

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )

    service.repo.get_by_symbol.assert_called_once_with(
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

    service.repo.update.assert_not_called()

    assert result == created_company

    db.commit.assert_called_once()

    db.refresh.assert_called_once_with(
        created_company
    )


def test_sync_company_updates_existing_company():

    service, db = make_service()

    existing_company = (
        make_existing_company()
    )

    service.repo.get_by_symbol.return_value = (
        existing_company
    )

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    updated_company = Mock()

    service.repo.update.return_value = (
        updated_company
    )

    result = service.sync_company("AAPL")

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )

    service.repo.get_by_symbol.assert_called_once_with(
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

    db.commit.assert_called_once()

    db.refresh.assert_called_once_with(
        updated_company
    )


def test_sync_company_normalizes_symbol():

    service, db = make_service()

    service.repo.get_by_symbol.return_value = None

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    service.repo.create.return_value = Mock()

    service.sync_company("  aapl  ")

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )

    service.repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.repo.create.assert_called_once()


def test_sync_company_cleans_provider_data():

    service, db = make_service()

    service.repo.get_by_symbol.return_value = None

    service.client.get_company_info.return_value = (
        make_company_data(
            symbol=" aapl ",
            name="  Apple     Inc.  ",
            sector=" Technology ",
            industry=" Consumer    Electronics ",
            country=" United States ",
            website=" https://www.apple.com ",
        )
    )

    service.repo.create.return_value = Mock()

    service.sync_company("AAPL")

    service.repo.create.assert_called_once_with(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
    )


def test_sync_company_rejects_invalid_company_data():

    service, db = make_service()

    service.client.get_company_info.return_value = (
        make_company_data(
            name=""
        )
    )

    service.repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Invalid company data",
    ):
        service.sync_company("AAPL")

    service.repo.create.assert_not_called()

    service.repo.update.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_sync_company_rejects_symbol_mismatch():

    service, db = make_service()

    service.client.get_company_info.return_value = (
        make_company_data(
            symbol="MSFT"
        )
    )

    with pytest.raises(
        ValueError,
        match="Provider returned symbol",
    ):
        service.sync_company("AAPL")

    service.repo.get_by_symbol.assert_not_called()

    service.repo.create.assert_not_called()

    service.repo.update.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_sync_company_rejects_empty_symbol():

    service, db = make_service()

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        service.sync_company("   ")

    service.client.get_company_info.assert_not_called()

    service.repo.get_by_symbol.assert_not_called()

    service.repo.create.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_sync_company_rolls_back_on_repository_error():

    service, db = make_service()

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    service.repo.get_by_symbol.return_value = None

    service.repo.create.side_effect = (
        RuntimeError("database error")
    )

    with pytest.raises(
        RuntimeError,
        match="database error",
    ):
        service.sync_company("AAPL")

    db.rollback.assert_called_once()

    db.commit.assert_not_called()


def test_sync_company_rolls_back_on_provider_error():

    service, db = make_service()

    service.client.get_company_info.side_effect = (
        RuntimeError("provider error")
    )

    with pytest.raises(
        RuntimeError,
        match="provider error",
    ):
        service.sync_company("AAPL")

    service.repo.get_by_symbol.assert_not_called()

    service.repo.create.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_sync_company_uses_processing_pipeline():

    service, db = make_service()

    raw_data = make_company_data()

    service.client.get_company_info.return_value = (
        raw_data
    )

    service.repo.get_by_symbol.return_value = None

    service.repo.create.return_value = Mock()

    result = service.sync_company("AAPL")

    assert isinstance(
        raw_data,
        CompanyData,
    )

    service.repo.create.assert_called_once()

    assert result is not None