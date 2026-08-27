from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

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
        """Return the latest ingested vintage not later than the requested as-of date.

        The query is performed in SQL so only the selected revision for each
        observation date is materialized. A vintage later than ``as_of`` can
        never enter the result set.
        """
        ranked = (
            select(
                MacroObservation,
                func.row_number()
                .over(
                    partition_by=MacroObservation.observation_date,
                    order_by=(
                        MacroObservation.vintage_date.desc(),
                        MacroObservation.id.desc(),
                    ),
                )
                .label("vintage_rank"),
            )
            .where(
                MacroObservation.series_id == series_id,
                MacroObservation.vintage_date <= as_of,
            )
            .subquery()
        )

        observation = aliased(MacroObservation)
        stmt = (
            select(observation)
            .join(ranked, observation.id == ranked.c.id)
            .where(ranked.c.vintage_rank == 1)
            .order_by(observation.observation_date.asc())
        )
        return list(self.db.scalars(stmt).all())

    def has_vintage(
        self,
        series_id: int,
        vintage_date: date,
    ) -> bool:
        """Return whether at least one observation from an exact vintage is stored."""
        return self.db.scalar(
            select(MacroObservation.id)
            .where(
                MacroObservation.series_id == series_id,
                MacroObservation.vintage_date == vintage_date,
            )
            .limit(1)
        ) is not None

    def create_observation(self, **kwargs) -> MacroObservation:
        observation = MacroObservation(**kwargs)
        self.db.add(observation)
        return observation
