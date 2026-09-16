from datetime import date, datetime, timezone
from unittest.mock import Mock

from quantcore.core.enums import FinancialStatementType
from quantcore.models.provenance import DataSource
from quantcore.schemas.income_statement import IncomeStatementData
from quantcore.services.financial_statement_revision import (
    cached_statement_known_at,
    build_statement_known_at_cache,
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


def test_build_statement_known_at_cache_preloads_accessions_once():
    from datetime import date
    from quantcore.schemas.income_statement import IncomeStatementData

    statements = [
        IncomeStatementData(fiscal_date=date(2024, 9, 28), accession_number="A"),
        IncomeStatementData(fiscal_date=date(2023, 9, 30), accession_number="B"),
    ]
    accepted_a = datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc)
    accepted_b = datetime(2023, 11, 3, 16, 30, tzinfo=timezone.utc)
    filing_repo = Mock()
    filing_repo.get_by_accessions.return_value = {
        "A": Mock(acceptance_datetime=accepted_a),
        "B": Mock(acceptance_datetime=accepted_b),
    }
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    cache = build_statement_known_at_cache(
        statements,
        source=DataSource.SEC,
        fetched_at=fetched_at,
        filing_repo=filing_repo,
    )

    assert cache == {"A": accepted_a, "B": accepted_b}
    filing_repo.get_by_accessions.assert_called_once_with({"A", "B"})
