from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.macro_ingestion import MacroIngestionState


class MacroIngestionStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, source: str, series_id: str) -> MacroIngestionState | None:
        return self.db.scalar(
            select(MacroIngestionState).where(
                MacroIngestionState.source == source,
                MacroIngestionState.series_id == series_id,
            )
        )

    def get_or_create(self, source: str, series_id: str) -> MacroIngestionState:
        state = self.get(source, series_id)
        if state is not None:
            return state

        state = MacroIngestionState(source=source, series_id=series_id)
        self.db.add(state)
        self.db.flush()
        return state

    def mark_attempt(self, state: MacroIngestionState, attempted_at: datetime) -> None:
        state.last_attempt_at = attempted_at
        state.updated_at = attempted_at

    def mark_success(
        self,
        state: MacroIngestionState,
        *,
        succeeded_at: datetime,
        vintage_date,
        records: int,
    ) -> None:
        state.last_success_at = succeeded_at
        state.last_success_vintage = vintage_date
        state.last_success_records = records
        state.consecutive_failures = 0
        state.last_error = None
        state.updated_at = succeeded_at

    def mark_failure(
        self,
        state: MacroIngestionState,
        *,
        failed_at: datetime,
        error: str,
    ) -> None:
        state.consecutive_failures += 1
        state.last_error = error[:2000]
        state.updated_at = failed_at
