from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quantcore.models.price import Price
from quantcore.models.price_observation_revision import PriceObservationRevision


class PriceObservationRevisionRepository:
    """Persistence operations for immutable market-price revisions."""

    def __init__(self, db: Session):
        self.db = db

    def get_next_revision_number(self, price_id: int) -> int:
        current = self.db.scalar(
            select(func.max(PriceObservationRevision.revision_number)).where(
                PriceObservationRevision.price_id == price_id
            )
        )
        return (current or 0) + 1

    def create(self, **kwargs) -> PriceObservationRevision:
        revision = PriceObservationRevision(**kwargs)
        self.db.add(revision)
        return revision

    def get_for_price(self, price_id: int) -> list[PriceObservationRevision]:
        stmt = (
            select(PriceObservationRevision)
            .where(PriceObservationRevision.price_id == price_id)
            .order_by(PriceObservationRevision.revision_number)
        )
        return list(self.db.scalars(stmt).all())

    def get_latest_for_security_as_of(
        self,
        security_id: int,
        as_of: datetime,
    ) -> list[PriceObservationRevision]:
        ranked = (
            select(
                PriceObservationRevision.id.label("revision_id"),
                func.row_number()
                .over(
                    partition_by=Price.date,
                    order_by=(
                        PriceObservationRevision.known_at.desc(),
                        PriceObservationRevision.revision_number.desc(),
                    ),
                )
                .label("row_number"),
            )
            .join(Price, Price.id == PriceObservationRevision.price_id)
            .where(
                Price.security_id == security_id,
                PriceObservationRevision.known_at <= as_of,
            )
            .subquery()
        )

        stmt = (
            select(PriceObservationRevision)
            .join(ranked, ranked.c.revision_id == PriceObservationRevision.id)
            .where(ranked.c.row_number == 1)
            .order_by(PriceObservationRevision.date)
        )
        return list(self.db.scalars(stmt).all())
