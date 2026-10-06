from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select, text

from quantcore.db.database import SessionLocal
from quantcore.models.ingestion import (
    IngestionJob,
    IngestionJobStatus,
    IngestionRun,
    IngestionRunStatus,
    IngestionOutcome,
    IngestionState,
)
from quantcore.models.ingestion_schedule import IngestionSchedule


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    normalized = _utc(value)
    return normalized.isoformat() if normalized is not None else None


def _error_category(error: str | None) -> str:
    """Return a low-risk failure category without exposing provider error text."""
    if not error:
        return "no_error_recorded"

    normalized = error.lower()
    categories = (
        (("timeout", "timed out", "readtimeout", "connecttimeout"), "timeout"),
        (("429", "rate limit", "too many requests", "throttl"), "rate_limited"),
        (("401", "unauthorized", "invalid api key", "authentication"), "authentication"),
        (("403", "forbidden", "permission denied"), "authorization"),
        (("404", "not found", "no data found"), "not_found_or_no_data"),
        (("connection refused", "could not connect", "connectionerror", "connection reset"), "connection"),
        (("ssl", "certificate verify", "tls"), "tls"),
        (("integrityerror", "uniqueviolation", "foreignkeyviolation", "constraint"), "database_constraint"),
        (("operationalerror", "sqlalchemy", "database", "postgres"), "database"),
        (("validation", "invalid value", "schema error", "parse error"), "validation_or_parsing"),
    )
    for markers, category in categories:
        if any(marker in normalized for marker in markers):
            return category
    return "other"



def _error_category_expression():
    """Categorize persisted error text in SQL without loading every state row."""
    normalized = func.lower(func.coalesce(IngestionState.last_error, ""))
    categories = (
        (("timeout", "timed out", "readtimeout", "connecttimeout"), "timeout"),
        (("429", "rate limit", "too many requests", "throttl"), "rate_limited"),
        (("401", "unauthorized", "invalid api key", "authentication"), "authentication"),
        (("403", "forbidden", "permission denied"), "authorization"),
        (("404", "not found", "no data found"), "not_found_or_no_data"),
        (("connection refused", "could not connect", "connectionerror", "connection reset"), "connection"),
        (("ssl", "certificate verify", "tls"), "tls"),
        (("integrityerror", "uniqueviolation", "foreignkeyviolation", "constraint"), "database_constraint"),
        (("operationalerror", "sqlalchemy", "database", "postgres"), "database"),
        (("validation", "invalid value", "schema error", "parse error"), "validation_or_parsing"),
    )
    whens = []
    for markers, category in categories:
        whens.append(
            (
                or_(*(normalized.like(f"%{marker}%") for marker in markers)),
                category,
            )
        )
    return case(*whens, else_="other")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only snapshot of QuantCore's persistent ingestion runtime. "
            "Does not expose credentials or raw provider error messages."
        )
    )
    parser.add_argument("--latest", type=int, default=20, help="Recent jobs/runs to include.")
    parser.add_argument(
        "--state-limit",
        type=int,
        default=50,
        help="Maximum problematic ingestion states to include (default: 50).",
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=300,
        help="Running-job heartbeat age considered stale (default: 300).",
    )
    parser.add_argument(
        "--queued-warning-seconds",
        type=int,
        default=900,
        help="Queued-job age considered delayed (default: 900).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        args.latest < 1
        or args.state_limit < 1
        or args.stale_after_seconds < 1
        or args.queued_warning_seconds < 1
    ):
        raise SystemExit("All numeric options must be greater than zero.")

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(seconds=args.stale_after_seconds)
    queued_cutoff = now - timedelta(seconds=args.queued_warning_seconds)
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))

        schedules = list(
            db.scalars(
                select(IngestionSchedule).order_by(
                    IngestionSchedule.enabled.desc(),
                    IngestionSchedule.next_run_at,
                    IngestionSchedule.id,
                )
            ).all()
        )
        jobs = list(
            db.scalars(
                select(IngestionJob)
                .order_by(IngestionJob.submitted_at.desc(), IngestionJob.id.desc())
                .limit(args.latest)
            ).all()
        )
        runs = list(
            db.scalars(
                select(IngestionRun)
                .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
                .limit(args.latest)
            ).all()
        )

        stale_jobs = list(
            db.scalars(
                select(IngestionJob).where(
                    IngestionJob.status == IngestionJobStatus.RUNNING,
                    (IngestionJob.heartbeat_at.is_(None))
                    | (IngestionJob.heartbeat_at < stale_cutoff),
                )
            ).all()
        )
        delayed_jobs = list(
            db.scalars(
                select(IngestionJob).where(
                    IngestionJob.status == IngestionJobStatus.QUEUED,
                    IngestionJob.submitted_at < queued_cutoff,
                )
            ).all()
        )
        overdue_schedules = [
            schedule
            for schedule in schedules
            if schedule.enabled and _utc(schedule.next_run_at) < now
        ]
        state_counts = db.execute(
            select(
                func.count(IngestionState.id),
                func.count(IngestionState.id).filter(
                    IngestionState.last_success_at.is_(None)
                ),
                func.count(IngestionState.id).filter(
                    IngestionState.consecutive_failures > 0
                ),
                func.count(IngestionState.id).filter(
                    IngestionState.last_outcome == IngestionOutcome.UNAVAILABLE
                ),
            )
        ).one()
        state_groups = db.execute(
            select(
                IngestionState.dataset,
                IngestionState.scope,
                func.count(IngestionState.id).label("total"),
                func.count(IngestionState.id)
                .filter(IngestionState.last_success_at.is_(None))
                .label("without_success"),
                func.count(IngestionState.id)
                .filter(IngestionState.consecutive_failures > 0)
                .label("with_consecutive_failures"),
                func.count(IngestionState.id)
                .filter(IngestionState.last_outcome == IngestionOutcome.UNAVAILABLE)
                .label("unavailable"),
            )
            .group_by(IngestionState.dataset, IngestionState.scope)
            .order_by(IngestionState.dataset, IngestionState.scope)
        ).all()
        problem_states = list(
            db.scalars(
                select(IngestionState)
                .where(
                    (
                        IngestionState.last_success_at.is_(None)
                        & (IngestionState.last_outcome != IngestionOutcome.UNAVAILABLE)
                    )
                    | (IngestionState.consecutive_failures > 0)
                )
                .order_by(
                    IngestionState.consecutive_failures.desc(),
                    IngestionState.last_attempt_at.desc().nullslast(),
                    IngestionState.id,
                )
                .limit(args.state_limit)
            ).all()
        )

        # Aggregate the full unresolved population in the database. Only the
        # bounded `problem_states` sample above is materialized in Python.
        problem_state_filter = (
            (
                IngestionState.last_success_at.is_(None)
                & (IngestionState.last_outcome != IngestionOutcome.UNAVAILABLE)
            )
            | (IngestionState.consecutive_failures > 0)
        )
        category_expression = _error_category_expression()
        category_rows = db.execute(
            select(
                IngestionState.dataset,
                category_expression.label("error_category"),
                func.count(IngestionState.id).label("count"),
            )
            .where(problem_state_filter)
            .group_by(IngestionState.dataset, category_expression)
            .order_by(IngestionState.dataset, category_expression)
        ).all()
        problem_error_categories: dict[str, int] = {}
        problem_error_categories_by_dataset: dict[str, dict[str, int]] = {}
        problem_states_total = 0
        for dataset, category, count in category_rows:
            dataset_name = dataset.value
            problem_states_total += count
            problem_error_categories[category] = (
                problem_error_categories.get(category, 0) + count
            )
            dataset_categories = problem_error_categories_by_dataset.setdefault(
                dataset_name, {}
            )
            dataset_categories[category] = count

        report = {
            "generated_at": now.isoformat(),
            "database": {"select_1": "ok"},
            "thresholds": {
                "stale_after_seconds": args.stale_after_seconds,
                "queued_warning_seconds": args.queued_warning_seconds,
            },
            "summary": {
                "enabled_schedules": sum(schedule.enabled for schedule in schedules),
                "total_schedules": len(schedules),
                "overdue_enabled_schedules": len(overdue_schedules),
                "stale_running_jobs": len(stale_jobs),
                "delayed_queued_jobs": len(delayed_jobs),
                "ingestion_states": state_counts[0],
                "states_without_success": state_counts[1],
                "states_with_consecutive_failures": state_counts[2],
                "states_unavailable": state_counts[3],
                "problem_states_total": problem_states_total,
                "problem_states_returned": len(problem_states),
            },
            "state_health": {
                "by_dataset_scope": [
                    {
                        "dataset": dataset.value,
                        "scope": scope.value,
                        "total": total,
                        "without_success": without_success,
                        "with_consecutive_failures": with_consecutive_failures,
                        "unavailable": unavailable,
                    }
                    for (
                        dataset,
                        scope,
                        total,
                        without_success,
                        with_consecutive_failures,
                        unavailable,
                    ) in state_groups
                ],
                "problem_error_categories": dict(sorted(problem_error_categories.items())),
                "problem_error_categories_by_dataset": {
                    dataset: dict(sorted(categories.items()))
                    for dataset, categories in sorted(
                        problem_error_categories_by_dataset.items()
                    )
                },
                "problem_states": [
                    {
                        "id": state.id,
                        "dataset": state.dataset.value,
                        "scope": state.scope.value,
                        "company_id": state.company_id,
                        "security_id": state.security_id,
                        "last_attempt_at": _iso(state.last_attempt_at),
                        "last_success_at": _iso(state.last_success_at),
                        "consecutive_failures": state.consecutive_failures,
                        "last_outcome": (
                            state.last_outcome.value
                            if state.last_outcome is not None
                            else None
                        ),
                        "next_check_at": _iso(state.next_check_at),
                        "last_success_records": state.last_success_records,
                        "has_error": bool(state.last_error),
                        "error_category": _error_category(state.last_error),
                    }
                    for state in problem_states
                ],
            },
            "schedules": [
                {
                    "id": schedule.id,
                    "name": schedule.name,
                    "dataset": schedule.dataset.value,
                    "enabled": schedule.enabled,
                    "next_run_at": _iso(schedule.next_run_at),
                    "last_triggered_at": _iso(schedule.last_triggered_at),
                    "symbols_mode": "explicit" if schedule.symbols is not None else "active_universe",
                    "symbol_count": len(schedule.symbols) if schedule.symbols is not None else None,
                    "target_limit": schedule.target_limit,
                    "interval_seconds": schedule.interval_seconds,
                }
                for schedule in schedules
            ],
            "recent_jobs": [
                {
                    "id": job.id,
                    "dataset": job.dataset.value,
                    "status": job.status.value,
                    "attempt_count": job.attempt_count,
                    "submitted_at": _iso(job.submitted_at),
                    "started_at": _iso(job.started_at),
                    "finished_at": _iso(job.finished_at),
                    "heartbeat_at": _iso(job.heartbeat_at),
                    "worker_id": job.worker_id,
                    "symbol_count": len(job.symbols) if job.symbols is not None else None,
                    "has_error": bool(job.error_summary),
                }
                for job in jobs
            ],
            "recent_runs": [
                {
                    "id": run.id,
                    "job_id": run.job_id,
                    "attempt_number": run.attempt_number,
                    "dataset": run.dataset.value if run.dataset is not None else None,
                    "status": run.status.value,
                    "started_at": _iso(run.started_at),
                    "finished_at": _iso(run.finished_at),
                    "eligible": run.eligible,
                    "attempted": run.attempted,
                    "succeeded": run.succeeded,
                    "skipped": run.skipped,
                    "failed": run.failed,
                    "has_error": bool(run.error_summary),
                }
                for run in runs
            ],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        # A successful database read and healthy processes do not imply that
        # ingestion is healthy. Persistent per-entity failures must make the
        # audit fail so automation/CI cannot treat an incomplete data platform
        # as operationally clean.
        return (
            1
            if (
                stale_jobs
                or delayed_jobs
                or overdue_schedules
                or state_counts[2] > 0
            )
            else 0
        )
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
