from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.security_identifier_history import (
    SecurityIdentifierHistory,
)


class SecurityIdentifierHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
    ) -> SecurityIdentifierHistory | None:
        stmt = select(SecurityIdentifierHistory).where(
            SecurityIdentifierHistory.security_id == security_id,
            SecurityIdentifierHistory.symbol == symbol,
            SecurityIdentifierHistory.exchange == exchange,
        )
        return self.db.scalar(stmt)

    def upsert(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
        observed_at: datetime,
    ) -> SecurityIdentifierHistory:
        history = self.get(security_id, symbol, exchange)

        if history is None:
            history = SecurityIdentifierHistory(
                security_id=security_id,
                symbol=symbol,
                exchange=exchange,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                is_current=True,
            )
            self.db.add(history)
            return history

        history.last_seen_at = observed_at
        history.is_current = True
        return history

    def mark_all_not_current(
        self,
        security_id: int,
    ) -> None:
        rows = self.db.scalars(
            select(SecurityIdentifierHistory).where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.is_current.is_(True),
            )
        ).all()

        for row in rows:
            row.is_current = False

    def mark_not_current(
        self,
        security_id: int,
        except_symbol: str,
        except_exchange: str,
    ) -> None:
        rows = self.db.scalars(
            select(SecurityIdentifierHistory).where(
                SecurityIdentifierHistory.security_id == security_id,
                ~(
                    (SecurityIdentifierHistory.symbol == except_symbol)
                    & (SecurityIdentifierHistory.exchange == except_exchange)
                ),
            )
        ).all()

        for row in rows:
            row.is_current = False
