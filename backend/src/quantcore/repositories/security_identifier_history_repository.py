from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.security_identifier_history import SecurityIdentifierHistory


class SecurityIdentifierHistoryRepository:
    """Historical listing identity (ticker/exchange) persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_current(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
    ) -> SecurityIdentifierHistory | None:
        stmt = select(SecurityIdentifierHistory).where(
            SecurityIdentifierHistory.security_id == security_id,
            SecurityIdentifierHistory.symbol == symbol,
            SecurityIdentifierHistory.exchange == exchange,
            SecurityIdentifierHistory.is_current.is_(True),
            SecurityIdentifierHistory.effective_to.is_(None),
        )
        return self.db.scalar(stmt)

    def get(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
    ) -> SecurityIdentifierHistory | None:
        return self.get_current(security_id, symbol, exchange)

    def upsert(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
        observed_at: datetime,
        *,
        source: str | None = None,
        source_reference: str | None = None,
    ) -> SecurityIdentifierHistory:
        history = self.get_current(security_id, symbol, exchange)
        observed_date = observed_at.date()

        if history is None:
            history = SecurityIdentifierHistory(
                security_id=security_id,
                symbol=symbol,
                exchange=exchange,
                effective_from=observed_date,
                effective_to=None,
                known_at=observed_at,
                source=source,
                source_reference=source_reference,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                is_current=True,
            )
            self.db.add(history)
            return history

        history.last_seen_at = observed_at
        history.source = source
        history.source_reference = source_reference
        history.is_current = True
        return history

    def mark_all_not_current(
        self,
        security_id: int,
        effective_to: date | None = None,
    ) -> None:
        rows = self.db.scalars(
            select(SecurityIdentifierHistory).where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.is_current.is_(True),
            )
        ).all()

        for row in rows:
            row.is_current = False
            if effective_to is not None and row.effective_to is None:
                if effective_to > row.effective_from:
                    row.effective_to = effective_to

    def mark_not_current(
        self,
        security_id: int,
        except_symbol: str,
        except_exchange: str,
        *,
        effective_to: date | None = None,
    ) -> None:
        rows = self.db.scalars(
            select(SecurityIdentifierHistory).where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.is_current.is_(True),
                ~(
                    (SecurityIdentifierHistory.symbol == except_symbol)
                    & (SecurityIdentifierHistory.exchange == except_exchange)
                ),
            )
        ).all()

        for row in rows:
            row.is_current = False
            if effective_to is not None and row.effective_to is None:
                if effective_to > row.effective_from:
                    row.effective_to = effective_to

    def get_for_security_as_of(
        self,
        security_id: int,
        *,
        effective_on: date,
    ) -> list[SecurityIdentifierHistory]:
        stmt = (
            select(SecurityIdentifierHistory)
            .where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.effective_from <= effective_on,
                (SecurityIdentifierHistory.effective_to.is_(None))
                | (SecurityIdentifierHistory.effective_to > effective_on),
            )
            .order_by(SecurityIdentifierHistory.effective_from.desc())
        )
        return list(self.db.scalars(stmt).all())
