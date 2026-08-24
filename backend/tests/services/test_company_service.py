from unittest.mock import Mock

from quantcore.models.provenance import CompanyField, DataSource

import pytest

from quantcore.schemas.company import CompanyData
from quantcore.services.company_service import CompanyService


def make_company_data():
    return CompanyData(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
    )


def make_company():
    company = Mock()

    company.id = 1
    company.name = "Old Apple Name"
    company.sector = "Old Sector"
    company.industry = "Old Industry"
    company.country = "United States"
    company.website = "https://old.apple.com"
    company.market_cap = 2_000_000_000_000

    return company


def make_security(company):
    security = Mock()

    security.id = 10
    security.company_id = company.id
    security.symbol = "AAPL"
    security.exchange = "NASDAQ"
    security.company = company

    return security


def make_service():

    db = Mock()

    service = CompanyService.__new__(
        CompanyService
    )

    service.db = db
    service.client = Mock()
    service.client.SOURCE = "YAHOO"
    service.security_repo = Mock()
    service.company_repo = Mock()
    service.provenance_repo = Mock()
    service.provenance_repo.get.return_value = None

    return service, db


def test_sync_company_updates_existing_company():

    service, db = make_service()

    company = make_company()
    security = make_security(company)

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    updated_company = Mock()

    service.company_repo.update.return_value = (
        updated_company
    )

    result = service.sync_company("AAPL")

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )

    service.company_repo.update.assert_called_once_with(
        company=company,
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
        cik=company.cik,
    )

    service.company_repo.create.assert_not_called()

    assert service.provenance_repo.upsert.call_count == 6
    assert result == updated_company

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(
        updated_company
    )


def test_sync_company_normalizes_symbol():

    service, db = make_service()

    company = make_company()
    security = make_security(company)

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    service.company_repo.update.return_value = (
        company
    )

    service.sync_company("  aapl  ")

    service.security_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_company_info.assert_called_once_with(
        "AAPL"
    )


def test_sync_company_security_not_found():

    service, db = make_service()

    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Security 'AAPL' not found",
    ):
        service.sync_company("AAPL")

    service.client.get_company_info.assert_not_called()

    service.company_repo.update.assert_not_called()

    db.commit.assert_not_called()


def test_sync_company_company_not_found():

    service, db = make_service()

    security = Mock()
    security.symbol = "AAPL"
    security.company = None

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    with pytest.raises(
        ValueError,
        match="Company for security 'AAPL' not found",
    ):
        service.sync_company("AAPL")

    service.client.get_company_info.assert_not_called()

    db.commit.assert_not_called()


def test_sync_company_rejects_empty_symbol():

    service, db = make_service()

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        service.sync_company("   ")

    service.security_repo.get_by_symbol.assert_not_called()

    service.client.get_company_info.assert_not_called()


def test_sync_company_rejects_provider_symbol_mismatch():

    service, db = make_service()

    company = make_company()
    security = make_security(company)

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    provider_data = make_company_data()

    provider_data = provider_data.model_copy(
        update={
            "symbol": "MSFT",
        }
    )

    service.client.get_company_info.return_value = (
        provider_data
    )

    with pytest.raises(
        ValueError,
        match="Provider returned symbol",
    ):
        service.sync_company("AAPL")

    service.company_repo.update.assert_not_called()

    db.commit.assert_not_called()


def test_sync_company_rolls_back_on_error():

    service, db = make_service()

    company = make_company()
    security = make_security(company)

    service.security_repo.get_by_symbol.return_value = (
        security
    )

    service.client.get_company_info.return_value = (
        make_company_data()
    )

    service.company_repo.update.side_effect = (
        RuntimeError("database error")
    )

    with pytest.raises(
        RuntimeError,
        match="database error",
    ):
        service.sync_company("AAPL")

    db.rollback.assert_called_once()

    db.commit.assert_not_called()

def test_sync_company_does_not_overwrite_sec_owned_name():

    service, db = make_service()

    company = make_company()
    company.name = "Apple Inc."
    security = make_security(company)

    service.security_repo.get_by_symbol.return_value = security
    service.client.get_company_info.return_value = make_company_data()

    sec_ownership = Mock()
    sec_ownership.source = DataSource.SEC

    def provenance_owner(company_id, field_name):
        if field_name == CompanyField.NAME:
            return sec_ownership
        return None

    service.provenance_repo.get.side_effect = provenance_owner
    service.company_repo.update.return_value = company

    result = service.sync_company("AAPL")

    assert result is company

    service.company_repo.update.assert_called_once_with(
        company=company,
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
        cik=company.cik,
    )

    # SEC remains the owner of name; Yahoo owns only the other fields.
    upserted_fields = [
        call.kwargs["field_name"]
        for call in service.provenance_repo.upsert.call_args_list
    ]
    assert CompanyField.NAME not in upserted_fields
    assert len(upserted_fields) == 5


def test_sync_company_records_yahoo_provenance_for_unowned_fields():

    service, db = make_service()

    company = make_company()
    security = make_security(company)

    service.security_repo.get_by_symbol.return_value = security
    service.client.get_company_info.return_value = make_company_data()
    service.company_repo.update.return_value = company

    service.sync_company("AAPL")

    fields = {
        call.kwargs["field_name"]
        for call in service.provenance_repo.upsert.call_args_list
    }

    assert fields == {
        CompanyField.NAME,
        CompanyField.SECTOR,
        CompanyField.INDUSTRY,
        CompanyField.COUNTRY,
        CompanyField.WEBSITE,
        CompanyField.MARKET_CAP,
    }

    assert all(
        call.kwargs["source"] == DataSource.YAHOO
        for call in service.provenance_repo.upsert.call_args_list
    )
