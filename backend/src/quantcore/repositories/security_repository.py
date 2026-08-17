from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.security import Security


class SecurityRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_symbol(
        self,
        symbol: str,
    ) -> Security | None:

        stmt = select(Security).where(
            Security.symbol == symbol
        )

        return self.db.scalar(stmt)

    def get_by_company_and_symbol(
        self,
        company_id: int,
        symbol: str,
    ) -> Security | None:

        stmt = select(Security).where(
            Security.company_id == company_id,
            Security.symbol == symbol,
        )

        return self.db.scalar(stmt)

    def get_by_symbols(
        self,
        symbols: list[str],
    ) -> list[Security]:

        if not symbols:
            return []

        stmt = select(Security).where(
            Security.symbol.in_(symbols)
        )

        return list(
            self.db.scalars(stmt).all()
        )

    def get_by_company_ids(
        self,
        company_ids: list[int],
    ) -> list[Security]:

        if not company_ids:
            return []

        stmt = select(Security).where(
            Security.company_id.in_(company_ids)
        )

        return list(
            self.db.scalars(stmt).all()
        )

    def create(
        self,
        company_id: int,
        symbol: str,
        exchange: str,
    ) -> Security:

        security = Security(
            company_id=company_id,
            symbol=symbol,
            exchange=exchange,
        )

        self.db.add(security)

        return security