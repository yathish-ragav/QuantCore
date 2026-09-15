from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.market_index import MarketIndex, MarketIndexConstituent


class MarketIndexRepository:
    """Persistence operations for market-index definitions and memberships."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> MarketIndex | None:
        return self.db.scalar(
            select(MarketIndex).where(MarketIndex.key == key)
        )

    def list_active(self) -> list[MarketIndex]:
        stmt = (
            select(MarketIndex)
            .where(MarketIndex.is_active.is_(True))
            .order_by(MarketIndex.name.asc(), MarketIndex.key.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create(
        self,
        *,
        key: str,
        name: str,
        provider: str,
        methodology_reference: str | None = None,
        source_reference: str | None = None,
    ) -> MarketIndex:
        index = MarketIndex(
            key=key,
            name=name,
            provider=provider,
            methodology_reference=methodology_reference,
            source_reference=source_reference,
        )
        self.db.add(index)
        return index

    def get_constituents_as_of(
        self,
        index_id: int,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> list[MarketIndexConstituent]:
        stmt = (
            select(MarketIndexConstituent)
            .where(
                MarketIndexConstituent.index_id == index_id,
                MarketIndexConstituent.effective_from <= effective_on,
                (MarketIndexConstituent.effective_to.is_(None))
                | (MarketIndexConstituent.effective_to > effective_on),
                MarketIndexConstituent.known_at <= known_at,
            )
            .order_by(
                MarketIndexConstituent.security_id.asc(),
                MarketIndexConstituent.id.asc(),
            )
        )
        return list(self.db.scalars(stmt).all())

    def get_constituents_for_security(
        self,
        index_id: int,
        security_id: int,
    ) -> list[MarketIndexConstituent]:
        stmt = (
            select(MarketIndexConstituent)
            .where(
                MarketIndexConstituent.index_id == index_id,
                MarketIndexConstituent.security_id == security_id,
            )
            .order_by(
                MarketIndexConstituent.effective_from.asc(),
                MarketIndexConstituent.id.asc(),
            )
        )
        return list(self.db.scalars(stmt).all())

    def create_constituent(
        self,
        *,
        index_id: int,
        security_id: int,
        effective_from: date,
        effective_to: date | None,
        weight,
        source_reference: str | None,
        known_at,
        observed_at,
    ) -> MarketIndexConstituent:
        constituent = MarketIndexConstituent(
            index_id=index_id,
            security_id=security_id,
            effective_from=effective_from,
            effective_to=effective_to,
            weight=weight,
            source_reference=source_reference,
            known_at=known_at,
            observed_at=observed_at,
        )
        self.db.add(constituent)
        return constituent
