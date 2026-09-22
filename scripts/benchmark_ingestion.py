from __future__ import annotations

import argparse
import json
import resource
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from sqlalchemy import event

from quantcore.db.database import SessionLocal, engine
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.ingestion.providers.sec import SECProvider
from quantcore.services.ingestion_orchestrator import IngestionOrchestrator
from quantcore.services.research_universe_service import ResearchUniverseService


DEFAULT_DATASETS = [
    IngestionDataset.INCOME_STATEMENT.value,
    IngestionDataset.BALANCE_SHEET.value,
    IngestionDataset.CASH_FLOW_STATEMENT.value,
    IngestionDataset.SEC_XBRL_FACTS.value,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure QuantCore ingestion throughput and hot-path resource usage."
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=[dataset.value for dataset in IngestionDataset],
        default=DEFAULT_DATASETS,
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--symbols", nargs="+", help="Explicit symbols to benchmark.")
    target.add_argument(
        "--limit",
        type=int,
        help="Maximum active securities to inspect (general-purpose mode).",
    )
    target.add_argument(
        "--cohort-size",
        type=int,
        help=(
            "Deterministic active, provider-classified common-stock cohort "
            "size for production validation."
        ),
    )
    refresh = parser.add_mutually_exclusive_group()
    refresh.add_argument(
        "--all",
        action="store_true",
        help="Refresh fresh datasets too; default is stale-only.",
    )
    refresh.add_argument(
        "--force-sync",
        action="store_true",
        help="Explicitly force synchronization even when dataset state is fresh.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path for the benchmark result.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    datasets = [IngestionDataset(value) for value in args.datasets]
    cohort = None
    benchmark_symbols = args.symbols
    benchmark_limit = args.limit
    if args.cohort_size is not None:
        db_for_cohort = SessionLocal()
        try:
            cohort = ResearchUniverseService(db_for_cohort).current_common_stock_cohort(
                size=args.cohort_size
            )
        finally:
            db_for_cohort.close()
        benchmark_symbols = list(cohort.symbols)
        benchmark_limit = None

    counters = Counter()
    statement_types = Counter()
    sql_seconds = 0.0
    http_hosts = Counter()
    http_paths = Counter()
    companyfacts_requests = 0
    http_seconds = 0.0
    http_429s = 0
    retry_sleep_seconds = 0.0
    commit_seconds = 0.0
    provider_seconds = Counter()
    commit_started_at = None
    dataset_seconds = Counter()
    original_session_request = requests.sessions.Session.request

    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal sql_seconds
        counters["sql"] += 1
        _context._quantcore_sql_started_at = time.perf_counter()
        keyword = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "EMPTY"
        statement_types[keyword] += 1

    def after_cursor_execute(_conn, _cursor, _statement, _parameters, _context, _executemany):
        nonlocal sql_seconds
        started_sql = getattr(_context, "_quantcore_sql_started_at", None)
        if started_sql is not None:
            sql_seconds += time.perf_counter() - started_sql

    def before_commit(_session):
        nonlocal commit_started_at
        commit_started_at = time.perf_counter()

    def after_commit(_session):
        nonlocal commit_seconds, commit_started_at
        counters["commits"] += 1
        if commit_started_at is not None:
            commit_seconds += time.perf_counter() - commit_started_at
            commit_started_at = None

    def after_rollback(_session):
        counters["rollbacks"] += 1

    def timed_session_request(session, method, url, *request_args, **request_kwargs):
        nonlocal companyfacts_requests, http_seconds, http_429s
        started_request = time.perf_counter()
        try:
            response = original_session_request(
                session, method, url, *request_args, **request_kwargs
            )
            if getattr(response, "status_code", None) == 429:
                http_429s += 1
            return response
        finally:
            elapsed_request = time.perf_counter() - started_request
            http_seconds += elapsed_request
            parsed = urlparse(url)
            host = parsed.netloc or "unknown"
            path = parsed.path or "/"
            http_hosts[host] += 1
            http_paths[path] += 1
            if "/api/xbrl/companyfacts/" in path:
                companyfacts_requests += 1

    def timed_provider_method(name, method):
        def wrapped(*method_args, **method_kwargs):
            started_method = time.perf_counter()
            try:
                return method(*method_args, **method_kwargs)
            finally:
                provider_seconds[name] += time.perf_counter() - started_method
        return wrapped

    original_provider_methods = {
        "income_statement": SECProvider.get_income_statements,
        "balance_sheet": SECProvider.get_balance_sheets,
        "cash_flow_statement": SECProvider.get_cash_flow_statements,
        "sec_xbrl_facts": SECProvider.get_sec_xbrl_fact_observations,
        "_get_company_facts": SECProvider._get_company_facts,
    }

    SECProvider.get_income_statements = timed_provider_method(
        "income_statement", original_provider_methods["income_statement"]
    )
    SECProvider.get_balance_sheets = timed_provider_method(
        "balance_sheet", original_provider_methods["balance_sheet"]
    )
    SECProvider.get_cash_flow_statements = timed_provider_method(
        "cash_flow_statement", original_provider_methods["cash_flow_statement"]
    )
    SECProvider.get_sec_xbrl_fact_observations = timed_provider_method(
        "sec_xbrl_facts", original_provider_methods["sec_xbrl_facts"]
    )
    SECProvider._get_company_facts = timed_provider_method(
        "_get_company_facts", original_provider_methods["_get_company_facts"]
    )

    def timed_sleep(seconds):
        nonlocal retry_sleep_seconds
        retry_sleep_seconds += max(float(seconds), 0.0)
        time.sleep(seconds)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    requests.sessions.Session.request = timed_session_request
    db = SessionLocal()
    orchestrator = IngestionOrchestrator(db)
    orchestrator._sleeper = timed_sleep
    original_sync = orchestrator._sync_with_retry

    def timed_sync(service, dataset, symbol):
        started_dataset = time.perf_counter()
        try:
            return original_sync(service, dataset, symbol)
        finally:
            dataset_seconds[dataset.value] += time.perf_counter() - started_dataset

    orchestrator._sync_with_retry = timed_sync
    event.listen(db, "before_commit", before_commit)
    event.listen(db, "after_commit", after_commit)
    event.listen(db, "after_rollback", after_rollback)

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    try:
        results = orchestrator.sync_market(
            datasets=datasets,
            symbols=benchmark_symbols,
            limit=benchmark_limit,
            only_stale=not (args.all or args.force_sync),
        )
    finally:
        elapsed = time.perf_counter() - started
        db.close()
        requests.sessions.Session.request = original_session_request
        for method_name, original_method in original_provider_methods.items():
            setattr(SECProvider, method_name, original_method)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)

    result_payload = {
        "started_at": started_at.isoformat(),
        "elapsed_seconds": round(elapsed, 6),
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "selection": (
            {
                "type": "deterministic_common_stock_cohort",
                "size": cohort.size,
                "fingerprint": cohort.fingerprint,
                "symbols": list(cohort.symbols),
            }
            if cohort is not None
            else {
                "type": "explicit_symbols" if args.symbols else "active_limit",
                "size": len(args.symbols) if args.symbols else args.limit,
            }
        ),
        "datasets": [
            {
                "dataset": result.dataset.value,
                "eligible": result.eligible,
                "attempted": result.attempted,
                "succeeded": result.succeeded,
                "skipped": result.skipped,
                "failed": result.failed,
                "run_id": result.run_id,
                "errors": list(result.errors),
            }
            for result in results
        ],
        "resource_usage": {
            "dataset_seconds": {key: round(value, 6) for key, value in sorted(dataset_seconds.items())},
            "sql_statements": counters["sql"],
            "sql_seconds": round(sql_seconds, 6),
            "sql_statement_types": dict(statement_types),
            "commits": counters["commits"],
            "commit_seconds": round(commit_seconds, 6),
            "provider_seconds": {key: round(value, 6) for key, value in sorted(provider_seconds.items())},
            "rollbacks": counters["rollbacks"],
            "http_requests": sum(http_hosts.values()),
            "http_seconds": round(http_seconds, 6),
            "http_429s": http_429s,
            "retry_sleep_seconds": round(retry_sleep_seconds, 6),
            "companyfacts_requests": companyfacts_requests,
            "http_hosts": dict(http_hosts),
        },
    }

    print(json.dumps(result_payload, indent=2, sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
