from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.market_index_source import MarketIndexDataSource


class MarketIndexDataSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> MarketIndexDataSource | None:
        return self.db.scalar(
            select(MarketIndexDataSource).where(MarketIndexDataSource.key == key)
        )

    def create(self, **kwargs) -> MarketIndexDataSource:
        source = MarketIndexDataSource(**kwargs)
        self.db.add(source)
        return source
