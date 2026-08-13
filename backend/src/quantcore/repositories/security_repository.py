from sqlalchemy.orm import Session

from quantcore.models.security import Security


class SecurityRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_symbol(
        self,
        symbol: str,
    ) -> Security | None:

        return (
            self.db.query(Security)
            .filter(Security.symbol == symbol)
            .first()
        )

    def get_by_company_and_symbol(
        self,
        company_id: int,
        symbol: str,
    ) -> Security | None:

        return (
            self.db.query(Security)
            .filter(
                Security.company_id == company_id,
                Security.symbol == symbol,
            )
            .first()
        )

    def get_by_company_ids(
        self,
        company_ids: list[int],
    ) -> list[Security]:

        if not company_ids:
            return []

        return (
            self.db.query(Security)
            .filter(Security.company_id.in_(company_ids))
            .all()
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