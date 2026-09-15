from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.market_index_load import MarketIndexDataLoad


class MarketIndexDataLoadRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_fingerprint(
        self, index_id: int, data_source_id: int, fingerprint: str
    ) -> MarketIndexDataLoad | None:
        return self.db.scalar(
            select(MarketIndexDataLoad).where(
                MarketIndexDataLoad.index_id == index_id,
                MarketIndexDataLoad.data_source_id == data_source_id,
                MarketIndexDataLoad.fingerprint == fingerprint,
            )
        )

    def create(self, **kwargs) -> MarketIndexDataLoad:
        load = MarketIndexDataLoad(**kwargs)
        self.db.add(load)
        return load
