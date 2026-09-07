from __future__ import annotations

import argparse
import logging
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.db.database import SessionLocal
from quantcore.services.ingestion_schedule_service import IngestionScheduleService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionSchedulerConfig:
    """Operational controls for the database-backed ingestion scheduler."""

    poll_interval_seconds: float = 5.0
    trigger_batch_size: int = 100

    def __post_init__(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise InvalidInputError("poll_interval_seconds must be greater than zero.")
        if self.trigger_batch_size < 1:
            raise InvalidInputError("trigger_batch_size must be at least one.")


class IngestionScheduler:
    """Create durable ingestion jobs from persistent schedules.

    The scheduler owns only trigger decisions. It never executes provider work;
    execution remains owned by the ingestion worker runtime.
    """

    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        config: IngestionSchedulerConfig | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.config = config or IngestionSchedulerConfig()
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Request graceful shutdown after the current trigger pass."""
        self._stop_event.set()

    def run_once(self) -> int:
        """Trigger all due schedules in one bounded database transaction."""
        db: Session = self.session_factory()
        try:
            triggers = IngestionScheduleService(db).trigger_due(
                now=datetime.now(timezone.utc),
                limit=self.config.trigger_batch_size,
            )
            for trigger in triggers:
                logger.info(
                    "Triggered ingestion schedule %s for job %s",
                    trigger.schedule_id,
                    trigger.job.job_id,
                )
            return len(triggers)
        finally:
            db.close()

    def run_forever(self) -> None:
        """Poll persistent schedules until stop() is requested."""
        logger.info("Starting ingestion scheduler")
        try:
            while not self._stop_event.is_set():
                try:
                    self.run_once()
                except Exception:
                    logger.exception("Ingestion scheduler failed while triggering schedules")
                self._stop_event.wait(self.config.poll_interval_seconds)
        finally:
            logger.info("Stopped ingestion scheduler")


def main() -> None:
    """CLI entrypoint for the production ingestion scheduler process."""
    parser = argparse.ArgumentParser(
        description="Run the QuantCore ingestion scheduler"
    )
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--trigger-batch-size", type=int, default=100)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    scheduler = IngestionScheduler(
        config=IngestionSchedulerConfig(
            poll_interval_seconds=args.poll_interval,
            trigger_batch_size=args.trigger_batch_size,
        )
    )

    def request_stop(signum, _frame) -> None:
        logger.info("Received signal %s; requesting scheduler shutdown", signum)
        scheduler.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    scheduler.run_forever()
