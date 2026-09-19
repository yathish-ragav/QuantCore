from datetime import date, datetime

from sqlalchemy import func, select
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

        # `known_at` is the knowledge boundary for this historical revision.
        # Once the listing is known, later observations must not move that
        # boundary forward: doing so would make the listing disappear from
        # valid point-in-time reads before the later observation.
        history.last_seen_at = max(history.last_seen_at, observed_at)
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

    def close_current(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
        *,
        effective_to: date,
    ) -> SecurityIdentifierHistory:
        """Close exactly one current listing interval.

        Identity transitions must not accidentally close another current
        listing if a security temporarily has more than one provider-visible
        listing. The effective end is exclusive.
        """
        history = self.get_current(security_id, symbol, exchange)
        if history is None:
            raise ValueError(
                f"Current identifier '{symbol}' on '{exchange}' not found for security {security_id}."
            )
        if effective_to <= history.effective_from:
            raise ValueError("effective_to must be after effective_from")

        history.is_current = False
        history.effective_to = effective_to
        return history

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
        known_at: datetime | None = None,
    ) -> list[SecurityIdentifierHistory]:
        """Return listing revisions visible at an effective/knowledge cutoff.

        When ``known_at`` is supplied, only revisions known by that timestamp
        are considered and the latest visible revision for each
        symbol/exchange is selected. This prevents later observations from
        leaking into historical research snapshots.
        """
        conditions = [
            SecurityIdentifierHistory.security_id == security_id,
            SecurityIdentifierHistory.effective_from <= effective_on,
            (SecurityIdentifierHistory.effective_to.is_(None))
            | (SecurityIdentifierHistory.effective_to > effective_on),
        ]
        if known_at is not None:
            conditions.append(SecurityIdentifierHistory.known_at <= known_at)

        ranked = (
            select(
                SecurityIdentifierHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=(
                        SecurityIdentifierHistory.symbol,
                        SecurityIdentifierHistory.exchange,
                    ),
                    order_by=(
                        SecurityIdentifierHistory.known_at.desc(),
                        SecurityIdentifierHistory.effective_from.desc(),
                        SecurityIdentifierHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(*conditions)
            .subquery()
        )
        stmt = (
            select(SecurityIdentifierHistory)
            .join(ranked, ranked.c.id == SecurityIdentifierHistory.id)
            .where(ranked.c.revision_rank == 1)
            .order_by(SecurityIdentifierHistory.effective_from.desc())
        )
        return list(self.db.scalars(stmt).all())
