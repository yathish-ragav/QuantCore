from datetime import date, datetime, timezone
from decimal import Decimal

from quantcore.models.macro import MacroObservation, MacroSeries
from quantcore.models.provenance import DataSource


def test_macro_series_has_source_aware_identity():
    table = MacroSeries.__table__
    constraint = next(
        item for item in table.constraints
        if getattr(item, "name", None) == "uq_macro_series_source_series_id"
    )
    assert [column.name for column in constraint.columns] == ["source", "series_id"]


def test_macro_observation_preserves_vintage_identity():
    observation = MacroObservation(
        series_id=1,
        observation_date=date(2020, 1, 1),
        value=Decimal("100.5"),
        realtime_start=date(2020, 2, 1),
        realtime_end=date(2020, 2, 1),
        vintage_date=date(2020, 2, 1),
        source=DataSource.FRED,
        fetched_at=datetime.now(timezone.utc),
    )
    assert observation.vintage_date == date(2020, 2, 1)
    assert observation.source is DataSource.FRED
