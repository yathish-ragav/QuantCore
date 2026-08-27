from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.core.enums import FinancialStatementType
from quantcore.repositories.financial_statement_revision_repository import (
    FinancialStatementRevisionRepository,
)


def make_repository():
    db = Mock()
    return FinancialStatementRevisionRepository(db), db


def test_get_next_revision_number_starts_at_one():
    repository, db = make_repository()
    db.scalar.return_value = None

    assert repository.get_next_revision_number(
        FinancialStatementType.INCOME, 10
    ) == 1


def test_get_next_revision_number_increments_existing_revision():
    repository, db = make_repository()
    db.scalar.return_value = 2

    assert repository.get_next_revision_number(
        FinancialStatementType.INCOME, 10
    ) == 3


def test_create_adds_revision_without_transaction_control():
    repository, db = make_repository()
    revision = repository.create(
        statement_type=FinancialStatementType.INCOME,
        statement_id=10,
        company_id=1,
        revision_number=1,
        fiscal_date=datetime(2024, 9, 28).date(),
        period_type="ANNUAL",
        known_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )

    db.add.assert_called_once_with(revision)
    assert revision.statement_id == 10
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_latest_for_company_as_of_returns_ranked_revisions():
    repository, db = make_repository()
    revision = Mock()
    db.scalars.return_value.all.return_value = [revision]

    result = repository.get_latest_for_company_as_of(
        1,
        FinancialStatementType.INCOME,
        datetime(2026, 1, 5, tzinfo=timezone.utc),
    )

    assert result == [revision]
    db.scalars.assert_called_once()
