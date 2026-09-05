import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import (
    DATASET_POLICIES,
    DATASET_SCOPES,
    IngestionDataset,
    IngestionScope,
)
from quantcore.models.ingestion import IngestionRunStatus, IngestionState
from quantcore.ingestion.retry import IngestionRetryPolicy
from quantcore.models.security import Security, SecurityStatus
from quantcore.repositories.ingestion_state_repository import (
    IngestionStateRepository,
)
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.services.balance_sheet_service import BalanceSheetService
from quantcore.services.cash_flow_statement_service import (
    CashFlowStatementService,
)
from quantcore.services.company_service import CompanyService
from quantcore.services.income_statement_service import IncomeStatementService
from quantcore.services.financial_statement_revision import FinancialStatementSyncResult
from quantcore.services.news_service import NewsService
from quantcore.services.price_service import PriceService, PriceSyncResult
from quantcore.services.corporate_action_service import CorporateActionService
from quantcore.services.sec_xbrl_fact_service import SECXBRLFactService, SECXBRLFactSyncResult
from quantcore.services.sec_filing_service import (
    SECFilingService,
    SECFilingSyncResult,
)


@dataclass(frozen=True)
class IngestionResult:
    dataset: IngestionDataset
    eligible: int
    attempted: int
    succeeded: int
    skipped: int
    failed: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class FreshnessView:
    dataset: IngestionDataset
    scope: IngestionScope
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_success_source: str | None
    last_success_records: int
    consecutive_failures: int
    last_error: str | None
    is_fresh: bool


class IngestionOrchestrator:
    """Coordinate existing dataset services without duplicating ingestion logic.

    The coordinator deliberately owns scheduling/freshness decisions only.
    Provider selection, normalization, validation, persistence and transaction
    boundaries remain inside the existing dataset services.
    """

    def __init__(
        self,
        db: Session,
        *,
        retry_policy: IngestionRetryPolicy | None = None,
        sleeper=time.sleep,
    ):
        self.db = db
        self.state_repo = IngestionStateRepository(db)
        self.retry_policy = retry_policy or IngestionRetryPolicy()
        self._sleeper = sleeper

    @staticmethod
    def _service_for(
        db: Session,
        dataset: IngestionDataset,
    ):
        services = {
            IngestionDataset.COMPANY: CompanyService,
            IngestionDataset.PRICE_HISTORY: PriceService,
            IngestionDataset.NEWS: NewsService,
            IngestionDataset.INCOME_STATEMENT: IncomeStatementService,
            IngestionDataset.CASH_FLOW_STATEMENT: CashFlowStatementService,
            IngestionDataset.BALANCE_SHEET: BalanceSheetService,
            IngestionDataset.SEC_FILINGS: SECFilingService,
            IngestionDataset.CORPORATE_ACTIONS: CorporateActionService,
            IngestionDataset.SEC_XBRL_FACTS: SECXBRLFactService,
        }
        return services[dataset](db)

    def _sync_with_retry(
        self,
        service,
        dataset: IngestionDataset,
        symbol: str,
    ) -> int:
        """Run one ingestion operation with bounded transient-failure retries."""
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                return self._sync(service, dataset, symbol)
            except Exception as exc:
                if not self.retry_policy.should_retry(exc, attempt):
                    raise

                # Dataset services own their transaction boundaries. Roll back
                # before retrying so a failed attempt cannot leak a partial
                # transaction into the next attempt.
                self.db.rollback()
                delay = self.retry_policy.delay_seconds(attempt)
                if delay > 0:
                    self._sleeper(delay)

        raise RuntimeError("Ingestion retry policy exhausted unexpectedly.")

    @staticmethod
    def _sync(
        service,
        dataset: IngestionDataset,
        symbol: str,
    ) -> int:
        if dataset is IngestionDataset.COMPANY:
            service.sync_company(symbol)
            return 1

        if dataset is IngestionDataset.PRICE_HISTORY:
            result = service.sync_price_history(symbol)
            if isinstance(result, PriceSyncResult):
                return result.records_processed
            return result

        if dataset is IngestionDataset.NEWS:
            return service.sync_news(symbol)

        if dataset is IngestionDataset.INCOME_STATEMENT:
            result = service.sync_income_statements(symbol)
            if isinstance(result, FinancialStatementSyncResult):
                return result.records_processed
            return len(result)

        if dataset is IngestionDataset.CASH_FLOW_STATEMENT:
            result = service.sync_cash_flow_statements(symbol)
            if isinstance(result, FinancialStatementSyncResult):
                return result.records_processed
            return len(result)

        if dataset is IngestionDataset.BALANCE_SHEET:
            result = service.sync_balance_sheets(symbol)
            if isinstance(result, FinancialStatementSyncResult):
                return result.records_processed
            return len(result)

        if dataset is IngestionDataset.SEC_FILINGS:
            result = service.sync_filings(symbol)
            if isinstance(result, SECFilingSyncResult):
                return result.records_processed
            return len(result)

        if dataset is IngestionDataset.CORPORATE_ACTIONS:
            result = service.sync_corporate_actions(symbol)
            return result.records_processed

        if dataset is IngestionDataset.SEC_XBRL_FACTS:
            result = service.sync_facts(symbol)
            if isinstance(result, SECXBRLFactSyncResult):
                return result.records_processed
            return len(result)

        raise InvalidInputError(
            f"Unsupported ingestion dataset: {dataset.value}"
        )

    def _is_fresh(
        self,
        state: IngestionState | None,
        dataset: IngestionDataset,
        now: datetime,
    ) -> bool:
        if state is None or state.last_success_at is None:
            return False

        return (
            now - state.last_success_at
            < DATASET_POLICIES[dataset].max_age
        )

    def get_freshness(
        self,
        symbol: str,
    ) -> list[FreshnessView]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        security = SecurityRepository(self.db).get_by_symbol(symbol)
        if security is None:
            return []

        now = datetime.now(timezone.utc)
        views: list[FreshnessView] = []

        for dataset in IngestionDataset:
            scope = DATASET_SCOPES[dataset]
            company_id = (
                security.company_id
                if scope is IngestionScope.COMPANY
                else None
            )
            security_id = (
                security.id
                if scope is IngestionScope.SECURITY
                else None
            )
            state = self.state_repo.get(
                dataset,
                company_id=company_id,
                security_id=security_id,
            )
            views.append(
                FreshnessView(
                    dataset=dataset,
                    scope=scope,
                    last_attempt_at=(
                        state.last_attempt_at if state else None
                    ),
                    last_success_at=(
                        state.last_success_at if state else None
                    ),
                    last_success_source=(
                        state.last_success_source if state else None
                    ),
                    last_success_records=(
                        state.last_success_records if state else 0
                    ),
                    consecutive_failures=(
                        state.consecutive_failures if state else 0
                    ),
                    last_error=state.last_error if state else None,
                    is_fresh=self._is_fresh(state, dataset, now),
                )
            )

        return views

    @staticmethod
    def _request_fingerprint(
        dataset: IngestionDataset,
        symbols: list[str] | None,
        limit: int | None,
        only_stale: bool,
    ) -> str:
        payload = {
            "dataset": dataset.value,
            "symbols": symbols,
            "limit": limit,
            "only_stale": only_stale,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _result_from_run(
        dataset: IngestionDataset,
        run,
    ) -> IngestionResult:
        errors = tuple(
            part.strip()
            for part in (run.error_summary or "").split("; ")
            if part.strip()
        )
        return IngestionResult(
            dataset=dataset,
            eligible=run.eligible,
            attempted=run.attempted,
            succeeded=run.succeeded,
            skipped=run.skipped,
            failed=run.failed,
            errors=errors,
        )

    def _get_or_create_run(
        self,
        dataset: IngestionDataset,
        *,
        idempotency_key: str | None,
        request_fingerprint: str,
    ) -> tuple[object, bool]:
        if idempotency_key is None:
            return (
                self.state_repo.create_run(dataset),
                False,
            )

        existing = self.state_repo.get_run_by_idempotency_key(
            dataset,
            idempotency_key,
        )
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise InvalidInputError(
                    "Idempotency key was already used for a different ingestion request."
                )
            if existing.status is IngestionRunStatus.RUNNING:
                raise InvalidInputError(
                    "An ingestion run with this idempotency key is already running."
                )
            return existing, True

        try:
            return (
                self.state_repo.create_run(
                    dataset,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                ),
                False,
            )
        except IntegrityError:
            self.db.rollback()
            existing = self.state_repo.get_run_by_idempotency_key(
                dataset,
                idempotency_key,
            )
            if existing is None:
                raise
            if existing.request_fingerprint != request_fingerprint:
                raise InvalidInputError(
                    "Idempotency key was already used for a different ingestion request."
                )
            if existing.status is IngestionRunStatus.RUNNING:
                raise InvalidInputError(
                    "An ingestion run with this idempotency key is already running."
                )
            return existing, True

    def recover_stale_runs(
        self,
        *,
        stale_after: timedelta,
        now: datetime | None = None,
    ) -> int:
        """Mark abandoned RUNNING executions as terminal failures.

        A process crash can leave an ingestion run in RUNNING forever. Recovery
        deliberately does not reuse its idempotency key: callers must create a
        new execution key for a new attempt, preserving the original audit
        record and idempotency contract.
        """
        if stale_after.total_seconds() <= 0:
            raise InvalidInputError("stale_after must be greater than zero.")

        recovered_at = now or datetime.now(timezone.utc)
        cutoff = recovered_at - stale_after
        runs = self.state_repo.get_running_runs_started_before(cutoff)

        for run in runs:
            self.state_repo.finish_run(
                run,
                status=IngestionRunStatus.FAILED,
                finished_at=recovered_at,
                attempted=run.attempted,
                succeeded=run.succeeded,
                skipped=run.skipped,
                failed=run.failed,
                error_summary=(
                    "Ingestion execution became stale before completion."
                ),
            )

        if runs:
            self.db.commit()

        return len(runs)

    def sync_market(
        self,
        *,
        datasets: list[IngestionDataset] | None = None,
        symbols: list[str] | None = None,
        limit: int | None = None,
        only_stale: bool = True,
        idempotency_key: str | None = None,
    ) -> list[IngestionResult]:
        """Run selected datasets across the active managed security universe.

        This is intentionally synchronous and bounded. It provides the
        production scheduling contract today while leaving concurrency,
        retries and distributed workers to a later execution layer.
        """
        selected = datasets or list(IngestionDataset)
        selected = list(dict.fromkeys(selected))

        if not selected:
            raise InvalidInputError("At least one ingestion dataset is required.")

        if limit is not None and limit <= 0:
            raise InvalidInputError("Limit must be greater than zero.")

        if idempotency_key is not None:
            idempotency_key = idempotency_key.strip()
            if not idempotency_key:
                raise InvalidInputError("Idempotency key must not be empty.")
            if len(idempotency_key) > 128:
                raise InvalidInputError("Idempotency key must be at most 128 characters.")

        normalized_symbols = None
        if symbols is not None:
            normalized_symbols = list(
                dict.fromkeys(
                    symbol.strip().upper()
                    for symbol in symbols
                    if symbol and symbol.strip()
                )
            )
            if not normalized_symbols:
                raise InvalidInputError(
                    "At least one valid symbol is required."
                )

        security_stmt = (
            select(Security)
            .where(Security.status == SecurityStatus.ACTIVE)
            .order_by(Security.id)
        )
        if normalized_symbols is not None:
            security_stmt = security_stmt.where(
                Security.symbol.in_(normalized_symbols)
            )
        if limit is not None:
            security_stmt = security_stmt.limit(limit)

        securities = list(self.db.scalars(security_stmt).all())
        now = datetime.now(timezone.utc)
        results: list[IngestionResult] = []

        for dataset in selected:
            scope = DATASET_SCOPES[dataset]
            request_fingerprint = self._request_fingerprint(
                dataset,
                normalized_symbols,
                limit,
                only_stale,
            )
            run, replayed = self._get_or_create_run(
                dataset,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if replayed:
                results.append(self._result_from_run(dataset, run))
                continue

            self.db.commit()

            attempted = succeeded = skipped = failed = 0
            errors: list[str] = []
            seen_entities: set[int] = set()

            try:
                for security in securities:
                    entity_id = (
                        security.company_id
                        if scope is IngestionScope.COMPANY
                        else security.id
                    )

                    # Company-scoped datasets are fetched once even when an
                    # issuer has multiple active listings.
                    if entity_id in seen_entities:
                        continue
                    seen_entities.add(entity_id)

                    state = self.state_repo.get(
                        dataset,
                        company_id=(
                            security.company_id
                            if scope is IngestionScope.COMPANY
                            else None
                        ),
                        security_id=(
                            security.id
                            if scope is IngestionScope.SECURITY
                            else None
                        ),
                    )

                    if (
                        only_stale
                        and self._is_fresh(state, dataset, now)
                    ):
                        skipped += 1
                        continue

                    attempted += 1
                    service = self._service_for(self.db, dataset)
                    state = self.state_repo.get_or_create(
                        dataset,
                        scope,
                        company_id=(
                            security.company_id
                            if scope is IngestionScope.COMPANY
                            else None
                        ),
                        security_id=(
                            security.id
                            if scope is IngestionScope.SECURITY
                            else None
                        ),
                    )
                    attempted_at = datetime.now(timezone.utc)
                    self.state_repo.mark_attempt(state, attempted_at)

                    try:
                        records = self._sync_with_retry(
                            service,
                            dataset,
                            security.symbol,
                        )
                        self.state_repo.mark_success(
                            state,
                            succeeded_at=datetime.now(timezone.utc),
                            source=getattr(
                                getattr(service, "provider", None),
                                "SOURCE",
                                getattr(
                                    getattr(service, "client", None),
                                    "SOURCE",
                                    None,
                                ),
                            ),
                            records=records,
                        )
                        self.db.commit()
                        succeeded += 1

                    except Exception as exc:
                        self.db.rollback()
                        state = self.state_repo.get_or_create(
                            dataset,
                            scope,
                            company_id=(
                                security.company_id
                                if scope is IngestionScope.COMPANY
                                else None
                            ),
                            security_id=(
                                security.id
                                if scope is IngestionScope.SECURITY
                                else None
                            ),
                        )
                        self.state_repo.mark_attempt(
                            state,
                            attempted_at,
                        )
                        self.state_repo.mark_failure(
                            state,
                            failed_at=datetime.now(timezone.utc),
                            error=str(exc),
                        )
                        self.db.commit()

                        failed += 1
                        errors.append(
                            f"{security.symbol}: {str(exc)[:500]}"
                        )

                status = (
                    IngestionRunStatus.COMPLETED_WITH_ERRORS
                    if failed
                    else IngestionRunStatus.COMPLETED
                )
                finished_at = datetime.now(timezone.utc)
                self.state_repo.finish_run(
                    run,
                    status=status,
                    finished_at=finished_at,
                    eligible=len(seen_entities),
                    attempted=attempted,
                    succeeded=succeeded,
                    skipped=skipped,
                    failed=failed,
                    error_summary="; ".join(errors) if errors else None,
                )
                self.db.commit()

            except Exception as exc:
                self.db.rollback()
                run = self.state_repo.get_run(run.id)
                if run is not None:
                    self.state_repo.finish_run(
                        run,
                        status=IngestionRunStatus.FAILED,
                        finished_at=datetime.now(timezone.utc),
                        eligible=len(seen_entities),
                        attempted=attempted,
                        succeeded=succeeded,
                        skipped=skipped,
                        failed=failed,
                        error_summary=str(exc),
                    )
                    self.db.commit()
                raise

            results.append(
                IngestionResult(
                    dataset=dataset,
                    eligible=len(seen_entities),
                    attempted=attempted,
                    succeeded=succeeded,
                    skipped=skipped,
                    failed=failed,
                    errors=tuple(errors),
                )
            )

        return results
