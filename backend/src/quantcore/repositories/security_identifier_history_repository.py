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
    ) -> None:
        rows = self.db.scalars(
            select(SecurityIdentifierHistory).where(
                SecurityIdentifierHistory.security_id == security_id,
                SecurityIdentifierHistory.is_current.is_(True),
            )
        ).all()

        for row in rows:
            # A current-source disappearance is an operational observation, not
            # authoritative evidence of the economic effective end date.
            # Never mutate effective_to here; authoritative identity events use
            # revise_current_with_effective_to(), which preserves bitemporal
            # knowledge history by appending a revision.
            row.is_current = False

    def revise_interval_with_effective_to(
        self,
        history: SecurityIdentifierHistory,
        *,
        effective_to: date,
        known_at: datetime,
        source: str | None = None,
        source_reference: str | None = None,
    ) -> SecurityIdentifierHistory:
        """Append a later-known closure revision without rewriting prior knowledge."""
        if effective_to <= history.effective_from:
            raise ValueError("effective_to must be after effective_from")
        if history.effective_to is not None and effective_to >= history.effective_to:
            raise ValueError("effective_to must revise an open or later-dated interval")
        if known_at.tzinfo is None:
            raise ValueError("known_at must be timezone-aware")
        if known_at <= history.known_at:
            raise ValueError("known_at must be later than the interval's prior knowledge boundary")

        history.is_current = False
        revised = SecurityIdentifierHistory(
            security_id=history.security_id,
            symbol=history.symbol,
            exchange=history.exchange,
            effective_from=history.effective_from,
            effective_to=effective_to,
            known_at=known_at,
            source=source,
            source_reference=source_reference,
            first_seen_at=history.first_seen_at,
            last_seen_at=max(history.last_seen_at, known_at),
            is_current=False,
        )
        self.db.add(revised)
        return revised

    def revise_current_with_effective_to(
        self,
        security_id: int,
        symbol: str,
        exchange: str,
        *,
        effective_to: date,
        known_at: datetime,
        source: str | None = None,
        source_reference: str | None = None,
    ) -> SecurityIdentifierHistory:
        """Record a later-known closure for the current listing interval."""
        history = self.get_current(security_id, symbol, exchange)
        if history is None:
            raise ValueError(
                f"Current identifier '{symbol}' on '{exchange}' not found for security {security_id}."
            )
        return self.revise_interval_with_effective_to(
            history,
            effective_to=effective_to,
            known_at=known_at,
            source=source,
            source_reference=source_reference,
        )

    def mark_not_current(
        self,
        security_id: int,
        except_symbol: str,
        except_exchange: str,
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
            # A current-source identity difference is not enough to establish
            # an economic effective end date. Preserve the open interval until
            # an authoritative identity transition supplies one.
            row.is_current = False

    def resolve_as_of(
        self,
        symbol: str,
        *,
        effective_on: date,
        known_at: datetime,
        exchange: str | None = None,
    ) -> list[SecurityIdentifierHistory]:
        """Resolve listing identity for one effective/knowledge boundary.

        The query is deliberately against historical listing rows rather than
        ``securities.symbol``. This makes a historical ticker change visible
        at its effective date without allowing today's ticker to leak backward.
        """
        # Resolve the latest bitemporal revision for each effective interval
        # before applying the effective-date predicate. A later-known revision
        # may backdate an interval's effective_to date; filtering the effective
        # interval first would let the older open-ended row leak into PIT reads.
        revision_conditions = [
            SecurityIdentifierHistory.symbol == symbol,
            SecurityIdentifierHistory.known_at <= known_at,
        ]
        if exchange is not None:
            revision_conditions.append(SecurityIdentifierHistory.exchange == exchange)

        ranked = (
            select(
                SecurityIdentifierHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=(
                        SecurityIdentifierHistory.security_id,
                        SecurityIdentifierHistory.symbol,
                        SecurityIdentifierHistory.exchange,
                        SecurityIdentifierHistory.effective_from,
                    ),
                    order_by=(
                        SecurityIdentifierHistory.known_at.desc(),
                        SecurityIdentifierHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(*revision_conditions)
            .subquery()
        )

        stmt = (
            select(SecurityIdentifierHistory)
            .join(ranked, ranked.c.id == SecurityIdentifierHistory.id)
            .where(
                ranked.c.revision_rank == 1,
                SecurityIdentifierHistory.effective_from <= effective_on,
                (SecurityIdentifierHistory.effective_to.is_(None))
                | (SecurityIdentifierHistory.effective_to > effective_on),
            )
            .order_by(
                SecurityIdentifierHistory.effective_from.desc(),
                SecurityIdentifierHistory.id.desc(),
            )
        )
        return list(self.db.scalars(stmt).all())

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
        revision_conditions = [SecurityIdentifierHistory.security_id == security_id]
        if known_at is not None:
            revision_conditions.append(SecurityIdentifierHistory.known_at <= known_at)

        # First select the latest known revision of each effective interval.
        # Only after that do we ask whether the selected revision was effective
        # on the requested date. This preserves bitemporal semantics when a
        # later source observation backdates an interval boundary.
        ranked = (
            select(
                SecurityIdentifierHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=(
                        SecurityIdentifierHistory.symbol,
                        SecurityIdentifierHistory.exchange,
                        SecurityIdentifierHistory.effective_from,
                    ),
                    order_by=(
                        SecurityIdentifierHistory.known_at.desc(),
                        SecurityIdentifierHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(*revision_conditions)
            .subquery()
        )
        stmt = (
            select(SecurityIdentifierHistory)
            .join(ranked, ranked.c.id == SecurityIdentifierHistory.id)
            .where(
                ranked.c.revision_rank == 1,
                SecurityIdentifierHistory.effective_from <= effective_on,
                (SecurityIdentifierHistory.effective_to.is_(None))
                | (SecurityIdentifierHistory.effective_to > effective_on),
            )
            .order_by(SecurityIdentifierHistory.effective_from.desc())
        )
        return list(self.db.scalars(stmt).all())
