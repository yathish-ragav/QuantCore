from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError
from quantcore.models.company import Company
from quantcore.models.security import Security, SecurityStatus


class SecurityRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_symbol(
        self,
        symbol: str,
    ) -> Security | None:
        stmt = (
            select(Security)
            .where(
                Security.symbol == symbol,
                Security.status == SecurityStatus.ACTIVE,
            )
            .order_by(Security.id)
        )
        securities = list(self.db.scalars(stmt).all())

        if len(securities) > 1:
            raise DataValidationError(
                f"Security symbol '{symbol}' is ambiguous across "
                "multiple active listings; specify the exchange."
            )

        return securities[0] if securities else None


    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Security]:
        """Search active listings by ticker, company name, or CIK.

        Exact ticker/CIK matches rank first, followed by ticker prefixes,
        company-name prefixes, and finally substring matches.  Results are
        security-level records so the caller never loses listing identity.
        """
        normalized = query.strip()
        if not normalized:
            return []

        normalized_upper = normalized.upper()
        pattern = f"%{normalized}%"
        prefix = f"{normalized}%"

        match = or_(
            func.upper(Security.symbol) == normalized_upper,
            Company.cik == normalized,
            func.upper(Security.symbol).like(f"{normalized_upper}%"),
            Company.name.ilike(prefix),
            Company.name.ilike(pattern),
            Security.exchange.ilike(pattern),
        )

        rank = case(
            (func.upper(Security.symbol) == normalized_upper, 0),
            (Company.cik == normalized, 1),
            (func.upper(Security.symbol).like(f"{normalized_upper}%"), 2),
            (Company.name.ilike(prefix), 3),
            (Company.name.ilike(pattern), 4),
            else_=5,
        )

        stmt = (
            select(Security)
            .join(Security.company)
            .where(
                Security.status == SecurityStatus.ACTIVE,
                match,
            )
            .order_by(rank, Company.name.asc(), Security.symbol.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_company_and_symbol(
        self,
        company_id: int,
        symbol: str,
    ) -> Security | None:
        stmt = select(Security).where(
            Security.company_id == company_id,
            Security.symbol == symbol,
            Security.status == SecurityStatus.ACTIVE,
        )

        return self.db.scalar(stmt)

    def get_by_company_symbol_exchange(
        self,
        company_id: int,
        symbol: str,
        exchange: str,
    ) -> Security | None:
        stmt = select(Security).where(
            Security.company_id == company_id,
            Security.symbol == symbol,
            Security.exchange == exchange,
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

        return list(self.db.scalars(stmt).all())

    def get_by_company_ids(
        self,
        company_ids: list[int],
    ) -> list[Security]:
        if not company_ids:
            return []

        stmt = select(Security).where(
            Security.company_id.in_(company_ids)
        )

        return list(self.db.scalars(stmt).all())

    def get_active_by_exchanges(
        self,
        exchanges: list[str],
    ) -> list[Security]:
        if not exchanges:
            return []

        stmt = select(Security).where(
            Security.exchange.in_(exchanges),
            Security.status == SecurityStatus.ACTIVE,
        )
        return list(self.db.scalars(stmt).all())

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
