from datetime import datetime

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from quantcore.models.price import Price


class PriceRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_for_security(
        self,
        security_id: int,
    ) -> list[Price]:

        stmt = (
            select(Price).where(Price.security_id == security_id).order_by(Price.date)
        )

        return list(self.db.scalars(stmt).all())

    def get_for_security_and_dates(
        self,
        security_id: int,
        dates: list[datetime],
    ) -> list[Price]:
        """Return existing prices for the supplied observation dates."""
        if not dates:
            return []

        calendar_dates = sorted({value.date().isoformat() for value in dates})
        stmt = (
            select(Price)
            .where(
                Price.security_id == security_id,
                cast(func.date(Price.date), String).in_(calendar_dates),
            )
            .order_by(Price.date)
        )

        return list(self.db.scalars(stmt).all())

    def get_by_security_and_date(
        self,
        security_id: int,
        date: datetime,
    ) -> Price | None:

        stmt = select(Price).where(
            Price.security_id == security_id,
            Price.date == date,
        )

        return self.db.scalar(stmt)

    def create(
        self,
        **kwargs,
    ) -> Price:

        price = Price(**kwargs)

        self.db.add(price)

        return price
