from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.repositories.universe_sync_repository import UniverseSyncRepository
from quantcore.universe.service import UniverseService


class UniverseSyncService:
    """Operational boundary around the existing security-universe sync."""

    SOURCE = "SEC"

    def __init__(self, db: Session):
        self.db = db
        self.repository = UniverseSyncRepository(db)
        self.universe_service = UniverseService(db)

    def sync(self) -> int:
        started_at = datetime.now(timezone.utc)
        run = self.repository.create_run(self.SOURCE, started_at)
        self.db.commit()

        try:
            processed = self.universe_service.sync()
            active_companies, active_securities, inactive_securities = (
                self.repository.get_counts()
            )
            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            run.records_processed = processed
            run.active_companies = active_companies
            run.active_securities = active_securities
            run.inactive_securities = inactive_securities
            self.db.commit()
            return processed
        except Exception as exc:
            self.db.rollback()
            failed_run = self.repository.get_latest()
            if failed_run is not None:
                failed_run.status = "FAILED"
                failed_run.completed_at = datetime.now(timezone.utc)
                failed_run.error = str(exc)[:2000]
                self.db.commit()
            raise

    def get_status(self):
        return self.repository.get_latest(), self._coverage()

    def _coverage(self) -> dict[str, int]:
        active_companies, active_securities, inactive_securities = (
            self.repository.get_counts()
        )
        return {
            "active_companies": active_companies,
            "active_securities": active_securities,
            "inactive_securities": inactive_securities,
        }
