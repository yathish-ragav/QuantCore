from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quantcore.db.database import Base
from quantcore.models.macro import MacroObservation, MacroSeries
from quantcore.models.provenance import DataSource
from quantcore.repositories.macro_repository import MacroRepository


def test_latest_as_of_selects_latest_vintage_per_observation_date():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        series = MacroSeries(
            series_id="GDP",
            source=DataSource.FRED,
            title="Gross Domestic Product",
            frequency="Quarterly",
            units="Billions",
        )
        db.add(series)
        db.flush()
        db.add_all([
            MacroObservation(
                series_id=series.id,
                observation_date=date(2020, 1, 1),
                value=Decimal("100"),
                realtime_start=date(2020, 2, 1),
                realtime_end=date(2020, 2, 1),
                vintage_date=date(2020, 2, 1),
                source=DataSource.FRED,
            ),
            MacroObservation(
                series_id=series.id,
                observation_date=date(2020, 1, 1),
                value=Decimal("110"),
                realtime_start=date(2020, 3, 1),
                realtime_end=date(2020, 3, 1),
                vintage_date=date(2020, 3, 1),
                source=DataSource.FRED,
            ),
        ])
        db.commit()

        result = MacroRepository(db).get_latest_as_of(series.id, date(2020, 3, 15))

        assert len(result) == 1
        assert result[0].value == Decimal("110")


def test_latest_as_of_excludes_future_revisions():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        series = MacroSeries(
            series_id="GDP",
            source=DataSource.FRED,
            title="Gross Domestic Product",
            frequency="Quarterly",
            units="Billions",
        )
        db.add(series)
        db.flush()
        db.add_all([
            MacroObservation(
                series_id=series.id,
                observation_date=date(2020, 1, 1),
                value=Decimal("100"),
                realtime_start=date(2020, 2, 1),
                realtime_end=date(2020, 2, 29),
                vintage_date=date(2020, 2, 1),
                source=DataSource.FRED,
            ),
            MacroObservation(
                series_id=series.id,
                observation_date=date(2020, 1, 1),
                value=Decimal("110"),
                realtime_start=date(2020, 3, 1),
                realtime_end=date(2020, 3, 31),
                vintage_date=date(2020, 3, 1),
                source=DataSource.FRED,
            ),
        ])
        db.commit()

        result = MacroRepository(db).get_latest_as_of(series.id, date(2020, 2, 29))

        assert len(result) == 1
        assert result[0].value == Decimal("100")
        assert result[0].vintage_date == date(2020, 2, 1)


def test_has_vintage_distinguishes_exact_ingested_snapshot():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        series = MacroSeries(
            series_id="GDP",
            source=DataSource.FRED,
            title="Gross Domestic Product",
            frequency="Quarterly",
            units="Billions",
        )
        db.add(series)
        db.flush()
        db.add(MacroObservation(
            series_id=series.id,
            observation_date=date(2020, 1, 1),
            value=Decimal("100"),
            realtime_start=date(2020, 2, 1),
            realtime_end=date(9999, 12, 31),
            vintage_date=date(2020, 2, 1),
            source=DataSource.FRED,
        ))
        db.commit()

        repo = MacroRepository(db)
        assert repo.has_vintage(series.id, date(2020, 2, 1)) is True
        assert repo.has_vintage(series.id, date(2020, 2, 2)) is False
