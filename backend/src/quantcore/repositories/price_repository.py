from datetime import datetime

from sqlalchemy.orm import Session

from quantcore.models.price import Price


class PriceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_company(self, company_id: int):
        return (
            self.db.query(Price)
            .filter(Price.company_id == company_id)
            .order_by(Price.date)
            .all()
        )

    def get_by_company_and_date(
        self,
        company_id: int,
        date: datetime,
    ):
        return (
            self.db.query(Price)
            .filter(
                Price.company_id == company_id,
                Price.date == date,
            )
            .first()
        )

    def create(self, **kwargs):
        price = Price(**kwargs)

        self.db.add(price)

        return price

    def commit(self):
        self.db.commit()