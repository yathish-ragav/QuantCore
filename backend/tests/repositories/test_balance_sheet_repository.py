from datetime import date
from unittest.mock import Mock

from quantcore.models.balance_sheet import BalanceSheet
from quantcore.repositories.balance_sheet_repository import BalanceSheetRepository


def make_repository():
    db = Mock()
    return BalanceSheetRepository(db), db


def test_get_by_company_and_date():
    repository, db = make_repository()
    statement = Mock(spec=BalanceSheet)
    db.scalar.return_value = statement

    result = repository.get_by_company_and_date(1, date(2024, 9, 28))

    db.scalar.assert_called_once()
    assert result == statement
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_for_company():
    repository, db = make_repository()
    statements = [Mock(spec=BalanceSheet), Mock(spec=BalanceSheet)]
    db.scalars.return_value = statements

    assert repository.get_for_company(1) == statements
    db.scalars.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_create_balance_sheet():
    repository, db = make_repository()
    statement = repository.create(
        company_id=1,
        fiscal_date=date(2024, 9, 28),
        total_assets=25000,
        total_liabilities=14000,
        total_equity=11000,
    )

    db.add.assert_called_once_with(statement)
    assert isinstance(statement, BalanceSheet)
    assert statement.total_assets == 25000
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
