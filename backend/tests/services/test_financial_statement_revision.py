from datetime import date, datetime, timezone
from unittest.mock import Mock

from quantcore.core.enums import FinancialStatementType
from quantcore.models.provenance import DataSource
from quantcore.schemas.income_statement import IncomeStatementData
from quantcore.services.financial_statement_revision import (
    cached_statement_known_at,
    resolve_statement_known_at,
)


def test_sec_statement_known_at_uses_filing_acceptance_timestamp():
    statement = IncomeStatementData(
        fiscal_date=date(2024, 9, 28),
        accession_number="0000320193-24-000123",
    )
    accepted = datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc)
    filing = Mock(acceptance_datetime=accepted)
    filing_repo = Mock()
    filing_repo.get_by_accession.return_value = filing
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert resolve_statement_known_at(
        statement, source=DataSource.SEC, fetched_at=fetched_at, filing_repo=filing_repo
    ) == accepted


def test_sec_statement_known_at_falls_back_to_fetch_time_without_filing_metadata():
    statement = IncomeStatementData(
        fiscal_date=date(2024, 9, 28),
        accession_number="0000320193-24-000123",
    )
    filing_repo = Mock()
    filing_repo.get_by_accession.return_value = None
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert resolve_statement_known_at(
        statement, source=DataSource.SEC, fetched_at=fetched_at, filing_repo=filing_repo
    ) == fetched_at


def test_cached_statement_known_at_reuses_accession_lookup():
    statement = IncomeStatementData(
        fiscal_date=date(2024, 9, 28),
        accession_number="0000320193-24-000123",
    )
    accepted = datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc)
    filing_repo = Mock()
    filing_repo.get_by_accession.return_value = Mock(acceptance_datetime=accepted)
    cache = {}
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = cached_statement_known_at(
        statement, source=DataSource.SEC, fetched_at=fetched_at, filing_repo=filing_repo, cache=cache
    )
    second = cached_statement_known_at(
        statement, source=DataSource.SEC, fetched_at=fetched_at, filing_repo=filing_repo, cache=cache
    )

    assert first == second == accepted
    filing_repo.get_by_accession.assert_called_once_with(statement.accession_number)
