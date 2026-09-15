from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quantcore.models.company import Company
from quantcore.models.security import Security, SecurityStatus
from quantcore.models.universe_sync import UniverseSyncRun, UniverseSyncRunStatus


class UniverseSyncRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, source: str, started_at: datetime) -> UniverseSyncRun:
        run = UniverseSyncRun(
            source=source,
            status=UniverseSyncRunStatus.RUNNING,
            started_at=started_at,
        )
        self.db.add(run)
        return run

    def get_latest(self) -> UniverseSyncRun | None:
        stmt = select(UniverseSyncRun).order_by(UniverseSyncRun.id.desc()).limit(1)
        return self.db.scalar(stmt)

    def get_counts(self) -> tuple[int, int, int]:
        active_companies = self.db.scalar(
            select(func.count(func.distinct(Security.company_id))).where(
                Security.status == SecurityStatus.ACTIVE
            )
        ) or 0
        active_securities = self.db.scalar(
            select(func.count(Security.id)).where(
                Security.status == SecurityStatus.ACTIVE
            )
        ) or 0
        inactive_securities = self.db.scalar(
            select(func.count(Security.id)).where(
                Security.status == SecurityStatus.INACTIVE
            )
        ) or 0
        return active_companies, active_securities, inactive_securities
