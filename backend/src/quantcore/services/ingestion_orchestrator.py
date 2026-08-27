from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import (
    DATASET_POLICIES,
    DATASET_SCOPES,
    IngestionDataset,
    IngestionScope,
)
from quantcore.models.ingestion import IngestionRunStatus, IngestionState
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
from quantcore.services.news_service import NewsService
from quantcore.services.price_service import PriceService
from quantcore.services.corporate_action_service import CorporateActionService
from quantcore.services.sec_filing_service import (
    SECFilingService,
    SECFilingSyncResult,
)


@dataclass(frozen=True)
class IngestionResult:
    dataset: IngestionDataset
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

    def __init__(self, db: Session):
        self.db = db
        self.state_repo = IngestionStateRepository(db)

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
        }
        return services[dataset](db)

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
            return service.sync_price_history(symbol)

        if dataset is IngestionDataset.NEWS:
            return service.sync_news(symbol)

        if dataset is IngestionDataset.INCOME_STATEMENT:
            return len(service.sync_income_statements(symbol))

        if dataset is IngestionDataset.CASH_FLOW_STATEMENT:
            return len(service.sync_cash_flow_statements(symbol))

        if dataset is IngestionDataset.BALANCE_SHEET:
            return len(service.sync_balance_sheets(symbol))

        if dataset is IngestionDataset.SEC_FILINGS:
            result = service.sync_filings(symbol)
            if isinstance(result, SECFilingSyncResult):
                return result.records_processed
            return len(result)

        if dataset is IngestionDataset.CORPORATE_ACTIONS:
            result = service.sync_corporate_actions(symbol)
            return result.records_processed

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

    def sync_market(
        self,
        *,
        datasets: list[IngestionDataset] | None = None,
        symbols: list[str] | None = None,
        limit: int | None = None,
        only_stale: bool = True,
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
            run = self.state_repo.create_run(dataset)
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
                        records = self._sync(
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
                    attempted=attempted,
                    succeeded=succeeded,
                    skipped=skipped,
                    failed=failed,
                    errors=tuple(errors),
                )
            )

        return results
