from __future__ import annotations

import argparse
import logging
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from quantcore.core.exceptions import IngestionJobClaimConflictError, InvalidInputError
from quantcore.db.database import SessionLocal
from quantcore.services.ingestion_execution_service import IngestionExecutionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionWorkerConfig:
    """Operational controls for the database-backed ingestion worker."""

    poll_interval_seconds: float = 2.0
    heartbeat_interval_seconds: float = 30.0
    stale_after_seconds: float = 300.0
    recovery_interval_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise InvalidInputError("poll_interval_seconds must be greater than zero.")
        if self.heartbeat_interval_seconds <= 0:
            raise InvalidInputError("heartbeat_interval_seconds must be greater than zero.")
        if self.stale_after_seconds <= self.heartbeat_interval_seconds:
            raise InvalidInputError(
                "stale_after_seconds must be greater than heartbeat_interval_seconds."
            )
        if self.recovery_interval_seconds <= 0:
            raise InvalidInputError("recovery_interval_seconds must be greater than zero.")


class IngestionWorker:
    """Run persistent ingestion jobs with a dedicated database session per action.

    The worker is intentionally a small operational runtime around the existing
    execution service. It does not own scheduling, provider logic, or business
    calculations, and it does not require a distributed queue.
    """

    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        worker_id: str | None = None,
        config: IngestionWorkerConfig | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.worker_id = worker_id or f"ingestion-worker:{uuid4().hex}"
        if not self.worker_id.strip() or len(self.worker_id) > 128:
            raise InvalidInputError("worker_id must be 1-128 characters.")
        self.config = config or IngestionWorkerConfig()
        self._stop_event = threading.Event()
        self._last_recovery_at = datetime.min.replace(tzinfo=timezone.utc)

    def stop(self) -> None:
        """Request graceful shutdown after the current job finishes."""
        self._stop_event.set()

    def run_once(self) -> bool:
        """Execute at most one queued job. Return whether work was claimed."""
        db: Session = self.session_factory()
        try:
            service = IngestionExecutionService(db)
            jobs = service.repository.get_queued_jobs(limit=1)
            if not jobs:
                return False
            try:
                claimed = service.claim(jobs[0].id, worker_id=self.worker_id)
            except IngestionJobClaimConflictError:
                return False
            job_id = claimed.job_id
            attempt_number = claimed.attempt_count
        finally:
            db.close()

        self._execute_with_heartbeat(job_id, attempt_number)
        return True

    def _execute_with_heartbeat(self, job_id: int, attempt_number: int) -> None:
        heartbeat_stop = threading.Event()

        def heartbeat_loop() -> None:
            while not heartbeat_stop.wait(self.config.heartbeat_interval_seconds):
                db = self.session_factory()
                try:
                    IngestionExecutionService(db).heartbeat(
                        job_id,
                        worker_id=self.worker_id,
                        attempt_number=attempt_number,
                    )
                except InvalidInputError:
                    logger.warning(
                        "Ingestion worker lost ownership of job %s", job_id
                    )
                    return
                except Exception:
                    logger.exception(
                        "Failed to heartbeat ingestion job %s", job_id
                    )
                finally:
                    db.close()

        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            name=f"quantcore-ingestion-heartbeat-{job_id}",
            daemon=True,
        )
        heartbeat_thread.start()
        db: Session = self.session_factory()
        try:
            IngestionExecutionService(db).execute_claimed(
                job_id,
                worker_id=self.worker_id,
                attempt_number=attempt_number,
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=self.config.heartbeat_interval_seconds)
            db.close()

    def recover_stale(self) -> int:
        """Recover jobs whose heartbeat lease has expired."""
        db: Session = self.session_factory()
        try:
            return IngestionExecutionService(db).recover_stale(
                stale_after=timedelta(seconds=self.config.stale_after_seconds)
            )
        finally:
            db.close()

    def run_forever(self) -> None:
        """Poll until stop() is requested, recovering abandoned jobs periodically."""
        logger.info("Starting ingestion worker %s", self.worker_id)
        try:
            while not self._stop_event.is_set():
                now = datetime.now(timezone.utc)
                if (
                    now - self._last_recovery_at
                ).total_seconds() >= self.config.recovery_interval_seconds:
                    # Recovery is an operational maintenance pass. A transient
                    # database/provider failure here must not terminate the
                    # worker process; the next scheduled pass can retry it.
                    self._last_recovery_at = now
                    try:
                        recovered = self.recover_stale()
                    except Exception:
                        logger.exception(
                            "Ingestion worker failed while recovering stale executions"
                        )
                    else:
                        if recovered:
                            logger.warning(
                                "Recovered %s stale ingestion execution(s)", recovered
                            )

                try:
                    worked = self.run_once()
                except Exception:
                    logger.exception("Ingestion worker failed while executing a job")
                    worked = False

                if not worked:
                    self._stop_event.wait(self.config.poll_interval_seconds)
        finally:
            logger.info("Stopped ingestion worker %s", self.worker_id)


def main() -> None:
    """CLI entrypoint for the production ingestion worker process."""
    parser = argparse.ArgumentParser(description="Run the QuantCore ingestion worker")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--heartbeat-interval", type=float, default=30.0)
    parser.add_argument("--stale-after", type=float, default=300.0)
    parser.add_argument("--recovery-interval", type=float, default=30.0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker = IngestionWorker(
        config=IngestionWorkerConfig(
            poll_interval_seconds=args.poll_interval,
            heartbeat_interval_seconds=args.heartbeat_interval,
            stale_after_seconds=args.stale_after,
            recovery_interval_seconds=args.recovery_interval,
        )
    )

    def request_stop(signum, _frame) -> None:
        logger.info("Received signal %s; requesting worker shutdown", signum)
        worker.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    worker.run_forever()
