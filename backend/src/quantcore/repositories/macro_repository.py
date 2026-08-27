from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.macro import MacroObservation, MacroSeries


class MacroRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_series(self, series_id: str, source: str):
        return self.db.scalar(
            select(MacroSeries).where(
                MacroSeries.series_id == series_id,
                MacroSeries.source == source,
            )
        )

    def create_series(self, **kwargs) -> MacroSeries:
        series = MacroSeries(**kwargs)
        self.db.add(series)
        return series

    def update_series(self, series: MacroSeries, **kwargs) -> MacroSeries:
        for key, value in kwargs.items():
            setattr(series, key, value)
        return series

    def get_observation(
        self,
        *,
        series_id: int,
        observation_date: date,
        vintage_date: date,
    ) -> MacroObservation | None:
        return self.db.scalar(
            select(MacroObservation).where(
                MacroObservation.series_id == series_id,
                MacroObservation.observation_date == observation_date,
                MacroObservation.vintage_date == vintage_date,
            )
        )

    def get_observations(
        self,
        series_id: int,
        *,
        vintage_date: date | None = None,
    ) -> list[MacroObservation]:
        stmt = select(MacroObservation).where(
            MacroObservation.series_id == series_id,
        )
        if vintage_date is not None:
            stmt = stmt.where(MacroObservation.vintage_date <= vintage_date)
        stmt = stmt.order_by(
            MacroObservation.observation_date.asc(),
            MacroObservation.vintage_date.asc(),
        )
        return list(self.db.scalars(stmt).all())

    def get_latest_as_of(
        self,
        series_id: int,
        as_of: date,
    ) -> list[MacroObservation]:
        observations = self.get_observations(series_id, vintage_date=as_of)
        latest: dict[date, MacroObservation] = {}
        for observation in observations:
            current = latest.get(observation.observation_date)
            if current is None or observation.vintage_date > current.vintage_date:
                latest[observation.observation_date] = observation
        return list(sorted(latest.values(), key=lambda item: item.observation_date))

    def create_observation(self, **kwargs) -> MacroObservation:
        observation = MacroObservation(**kwargs)
        self.db.add(observation)
        return observation
