from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from typing import Any

from quantcore.core.config import settings
from quantcore.core.exceptions import InvalidInputError
from quantcore.db.database import SessionLocal
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.services.ingestion_schedule_service import IngestionScheduleService

logger = logging.getLogger(__name__)
SCHEDULES_ENV = "QUANTCORE_INGESTION_SCHEDULES_JSON"


def _parse_datetime(value: Any, *, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{field} must be an ISO-8601 datetime string.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidInputError(f"{field} must be a valid ISO-8601 datetime.") from exc
    if parsed.tzinfo is None:
        raise InvalidInputError(f"{field} must include a timezone offset.")
    return parsed


def _load_specs(raw: str | None) -> list[dict[str, Any]]:
    if raw is None or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidInputError(
            f"{SCHEDULES_ENV} must contain valid JSON."
        ) from exc
    if not isinstance(value, list):
        raise InvalidInputError(f"{SCHEDULES_ENV} must contain a JSON array.")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise InvalidInputError(
                f"{SCHEDULES_ENV}[{index}] must be a JSON object."
            )
    return value


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    required = {"name", "dataset", "interval_seconds"}
    missing = sorted(required - spec.keys())
    if missing:
        raise InvalidInputError(
            f"Ingestion schedule is missing required fields: {', '.join(missing)}."
        )

    dataset_value = spec["dataset"]
    try:
        dataset = IngestionDataset(str(dataset_value))
    except ValueError as exc:
        raise InvalidInputError(
            f"Unsupported ingestion dataset: {dataset_value!r}."
        ) from exc

    symbols = spec.get("symbols")
    if symbols is not None:
        if not isinstance(symbols, list) or not all(isinstance(item, str) for item in symbols):
            raise InvalidInputError("Ingestion schedule symbols must be an array of strings.")
        symbols = symbols

    interval = spec["interval_seconds"]
    if isinstance(interval, bool) or not isinstance(interval, int):
        raise InvalidInputError("Ingestion schedule interval_seconds must be an integer.")

    limit = spec.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)):
        raise InvalidInputError("Ingestion schedule limit must be an integer.")

    only_stale = spec.get("only_stale", True)
    enabled = spec.get("enabled", True)
    if not isinstance(only_stale, bool) or not isinstance(enabled, bool):
        raise InvalidInputError("Ingestion schedule only_stale and enabled must be booleans.")

    next_run_at = _parse_datetime(spec.get("next_run_at"), field="next_run_at")

    return {
        "name": spec["name"],
        "dataset": dataset,
        "interval_seconds": interval,
        "next_run_at": next_run_at,
        "symbols": symbols,
        "limit": limit,
        "only_stale": only_stale,
        "enabled": enabled,
    }


def bootstrap_schedules(*, raw: str | None = None) -> int:
    """Create declared schedules once, failing closed on configuration drift.

    Existing schedules are left untouched when their declarative configuration
    matches. A name collision with different settings is treated as deployment
    drift rather than silently mutating a production schedule.
    """
    configured_raw = raw if raw is not None else settings.QUANTCORE_INGESTION_SCHEDULES_JSON
    specs = [_normalize_spec(item) for item in _load_specs(configured_raw)]
    if not specs:
        logger.warning(
            "No ingestion schedules configured; %s is empty or unset.",
            SCHEDULES_ENV,
        )
        return 0

    names: set[str] = set()
    db = SessionLocal()
    try:
        service = IngestionScheduleService(db)
        to_create: list[dict[str, Any]] = []

        # Validate all existing names before creating anything so one bad
        # schedule cannot leave a partially bootstrapped deployment.
        for spec in specs:
            name = service._normalize_name(spec["name"])
            if name in names:
                raise InvalidInputError(f"Duplicate ingestion schedule name: {name}.")
            names.add(name)

            existing = service.repository.get_by_name(name)
            if existing is None:
                to_create.append(spec)
                continue

            comparable = {
                "dataset": existing.dataset,
                "symbols": service._normalize_symbols(existing.symbols),
                "limit": existing.target_limit,
                "only_stale": existing.only_stale,
                "interval_seconds": existing.interval_seconds,
                "enabled": existing.enabled,
            }
            expected = {
                "dataset": spec["dataset"],
                "symbols": service._normalize_symbols(spec["symbols"]),
                "limit": spec["limit"],
                "only_stale": spec["only_stale"],
                "interval_seconds": spec["interval_seconds"],
                "enabled": spec["enabled"],
            }
            if comparable != expected:
                raise InvalidInputError(
                    f"Ingestion schedule '{name}' already exists with different configuration."
                )

        created = 0
        for spec in to_create:
            service.create(**spec)
            created += 1
            logger.info("Created ingestion schedule name=%s", spec["name"].strip())

        for spec in specs:
            if spec not in to_create:
                logger.info("Ingestion schedule already configured name=%s", spec["name"].strip())

        return created
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap declarative QuantCore ingestion schedules"
    )
    parser.add_argument(
        "--schedules-json",
        help=f"JSON schedule array; defaults to ${SCHEDULES_ENV}",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    created = bootstrap_schedules(raw=args.schedules_json)
    logger.info("Ingestion schedule bootstrap complete created=%s", created)


if __name__ == "__main__":
    main()
