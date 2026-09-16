from sqlalchemy import BigInteger

from quantcore.models.company import Company


def test_company_market_cap_is_nullable_big_integer():
    column = Company.__table__.c.market_cap

    assert isinstance(column.type, BigInteger)
    assert column.nullable is True
