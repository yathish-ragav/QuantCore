from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.ingestion.providers.macro_factory import MacroProviderFactory
from quantcore.models.provenance import DataSource
from quantcore.repositories.macro_repository import MacroRepository
from quantcore.schemas.macro import MacroObservationData, MacroSeriesData


@dataclass(frozen=True)
class MacroSyncResult:
    created: int
    unchanged: int
    records_processed: int
    vintage_date: date


class MacroService:
    def __init__(self, db: Session):
        self.db = db
        self.provider = MacroProviderFactory.get_provider()
        self.repo = MacroRepository(db)

    def get_series(self, series_id: str):
        normalized = series_id.strip().upper()
        if not normalized:
            raise InvalidInputError("Series ID must not be empty.")
        series = self.repo.get_series(normalized, self.provider.SOURCE)
        if series is None:
            raise ResourceNotFoundError(f"Macro series not found: {normalized}")
        return series

    def get_observations(self, series_id: str, *, as_of: date | None = None):
        series = self.get_series(series_id)
        if as_of is None:
            return self.repo.get_latest_as_of(series.id, date.today())
        return self.repo.get_latest_as_of(series.id, as_of)

    def sync_series(
        self,
        series_id: str,
        *,
        vintage_date: date | None = None,
    ) -> MacroSyncResult:
        normalized = series_id.strip().upper()
        if not normalized:
            raise InvalidInputError("Series ID must not be empty.")

        vintage = vintage_date or date.today()
        try:
            series_data = self.provider.get_series(normalized)
            observations = self.provider.get_observations(
                normalized,
                vintage_date=vintage,
            )
            if not isinstance(series_data, MacroSeriesData):
                raise DataValidationError("Macro provider returned invalid series metadata.")
            if not isinstance(observations, list):
                raise DataValidationError("Macro provider returned invalid observations.")
            if any(not isinstance(item, MacroObservationData) for item in observations):
                raise DataValidationError("Macro provider returned an invalid observation object.")

            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)
            series = self.repo.get_series(normalized, self.provider.SOURCE)
            metadata = series_data.model_dump()
            metadata.update(
                source=source,
                fetched_at=fetched_at,
            )
            if series is None:
                series = self.repo.create_series(**metadata)
                self.db.flush()
            else:
                self.repo.update_series(series, **metadata)

            created = unchanged = 0
            for data in observations:
                existing = self.repo.get_observation(
                    series_id=series.id,
                    observation_date=data.observation_date,
                    vintage_date=data.vintage_date,
                )
                if existing is not None:
                    existing.value = data.value
                    existing.realtime_start = data.realtime_start
                    existing.realtime_end = data.realtime_end
                    existing.source = source
                    existing.fetched_at = fetched_at
                    unchanged += 1
                    continue

                self.repo.create_observation(
                    series_id=series.id,
                    observation_date=data.observation_date,
                    value=data.value,
                    realtime_start=data.realtime_start,
                    realtime_end=data.realtime_end,
                    vintage_date=data.vintage_date,
                    source=source,
                    fetched_at=fetched_at,
                    source_reference=f"FRED:{normalized}:vintage:{vintage.isoformat()}",
                )
                created += 1

            self.db.commit()
            return MacroSyncResult(
                created=created,
                unchanged=unchanged,
                records_processed=len(observations),
                vintage_date=vintage,
            )
        except Exception:
            self.db.rollback()
            raise
