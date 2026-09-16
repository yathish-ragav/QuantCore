from sqlalchemy import BigInteger

from quantcore.models.income_statement import IncomeStatement


def test_income_statement_shares_outstanding_uses_big_integer():
    column = IncomeStatement.__table__.c.shares_outstanding

    assert isinstance(column.type, BigInteger)


def test_income_statement_weighted_average_shares_uses_big_integer():
    column = IncomeStatement.__table__.c.weighted_average_shares_outstanding

    assert isinstance(column.type, BigInteger)
