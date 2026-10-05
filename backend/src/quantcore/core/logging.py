from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from quantcore.core.config import settings


_SAFE_EXTRA_FIELDS = {
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "job_id",
    "worker_id",
    "attempt",
    "dataset",
    "run_id",
    "eligible",
    "attempted",
    "succeeded",
    "skipped",
    "failed",
    "schedule_id",
    "environment",
}


class JsonFormatter(logging.Formatter):
    """Emit stable, machine-readable operational logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": settings.ENVIRONMENT,
        }

        for field in _SAFE_EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    """Configure process-wide application logging once at process startup."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Unsupported LOG_LEVEL: {settings.LOG_LEVEL!r}")

    formatter: logging.Formatter
    if settings.LOG_FORMAT.strip().lower() == "json":
        formatter = JsonFormatter()
    elif settings.LOG_FORMAT.strip().lower() == "text":
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    else:
        raise ValueError(f"Unsupported LOG_FORMAT: {settings.LOG_FORMAT!r}")

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        root.addHandler(handler)
    for handler in root.handlers:
        handler.setFormatter(formatter)
        handler.setLevel(level)
