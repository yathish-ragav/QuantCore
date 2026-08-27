from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from quantcore.models.provenance import DataSource
from quantcore.schemas.macro import MacroObservationData, MacroSeriesData
from quantcore.services.macro_service import MacroService, MacroSyncResult


def make_service():
    db = Mock()
    service = MacroService.__new__(MacroService)
    service.db = db
    service.provider = Mock()
    service.provider.SOURCE = "FRED"
    service.repo = Mock()
    return service, db


def series_data():
    return MacroSeriesData(
        series_id="GDP",
        title="Gross Domestic Product",
        frequency="Quarterly",
        units="Billions of Dollars",
    )


def observation_data(vintage=date(2026, 8, 27), value="100"):
    return MacroObservationData(
        series_id="GDP",
        observation_date=date(2026, 4, 1),
        value=Decimal(value),
        realtime_start=vintage,
        realtime_end=vintage,
        vintage_date=vintage,
    )


def test_sync_series_creates_series_and_vintage_observation():
    service, db = make_service()
    service.provider.get_series.return_value = series_data()
    service.provider.get_observations.return_value = [observation_data()]
    service.repo.get_series.return_value = None
    service.repo.get_observation.return_value = None

    result = service.sync_series("gdp", vintage_date=date(2026, 8, 27))

    assert result == MacroSyncResult(
        created=1,
        unchanged=0,
        records_processed=1,
        vintage_date=date(2026, 8, 27),
    )
    service.repo.create_series.assert_called_once()
    service.repo.create_observation.assert_called_once()
    kwargs = service.repo.create_observation.call_args.kwargs
    assert kwargs["source"] is DataSource.FRED
    db.commit.assert_called_once()


def test_sync_series_is_idempotent_for_same_vintage():
    service, db = make_service()
    series = Mock(id=7)
    service.provider.get_series.return_value = series_data()
    service.provider.get_observations.return_value = [observation_data()]
    service.repo.get_series.return_value = series
    service.repo.get_observation.return_value = Mock()

    result = service.sync_series("GDP", vintage_date=date(2026, 8, 27))

    assert result.created == 0
    assert result.unchanged == 1
    service.repo.create_observation.assert_not_called()
    db.commit.assert_called_once()


def test_get_observations_as_of_uses_point_in_time_repository_query():
    service, _ = make_service()
    series = Mock(id=7)
    service.repo.get_series.return_value = series
    service.repo.get_latest_as_of.return_value = [Mock()]

    result = service.get_observations("GDP", as_of=date(2024, 1, 1))

    assert len(result) == 1
    service.repo.get_latest_as_of.assert_called_once_with(7, date(2024, 1, 1))
