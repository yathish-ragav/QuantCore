from datetime import date, datetime

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from quantcore.core.enums import FinancialPeriodType, FinancialStatementType, SecurityType
from quantcore.ingestion.datasets import DATASET_POLICIES, IngestionDataset
from quantcore.models.balance_sheet import BalanceSheet
from quantcore.models.cash_flow_statement import CashFlowStatement
from quantcore.models.company import Company
from quantcore.models.financial_statement_revision import FinancialStatementRevision
from quantcore.models.ingestion import IngestionState
from quantcore.models.income_statement import IncomeStatement
from quantcore.models.news import News
from quantcore.models.price import Price
from quantcore.models.price_observation_revision import PriceObservationRevision
from quantcore.models.sec_filing import SECFiling
from quantcore.models.sec_xbrl_fact import SECXBRLFactObservation
from quantcore.models.provenance import DataSource
from quantcore.models.security import Security, SecurityStatus
from quantcore.models.security_classification_history import SecurityClassificationHistory
from quantcore.models.security_identifier_history import SecurityIdentifierHistory


class ResearchUniverseRepository:
    """Database selection primitives for current and point-in-time universes."""

    def __init__(self, db: Session):
        self.db = db

    def get_current_common_stock_cohort(self, *, size: int) -> list[Security]:
        """Return a deterministic active cohort with provider-owned classification."""
        stmt = (
            select(Security)
            .where(
                Security.status == SecurityStatus.ACTIVE,
                Security.security_type == SecurityType.COMMON_STOCK,
                Security.security_type_source == DataSource.MASSIVE,
                Security.security_type_fetched_at.is_not(None),
            )
            .order_by(Security.id)
            .limit(size)
        )
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def _persisted_row_exists(dataset: IngestionDataset):
        if dataset is IngestionDataset.COMPANY:
            return exists(select(1).where(Company.id == Security.company_id))
        if dataset is IngestionDataset.PRICE_HISTORY:
            return exists(select(1).where(Price.security_id == Security.id))
        if dataset is IngestionDataset.INCOME_STATEMENT:
            return exists(select(1).where(IncomeStatement.company_id == Security.company_id))
        if dataset is IngestionDataset.CASH_FLOW_STATEMENT:
            return exists(select(1).where(CashFlowStatement.company_id == Security.company_id))
        if dataset is IngestionDataset.BALANCE_SHEET:
            return exists(select(1).where(BalanceSheet.company_id == Security.company_id))
        if dataset is IngestionDataset.SEC_FILINGS:
            return exists(select(1).where(SECFiling.company_id == Security.company_id))
        if dataset is IngestionDataset.SEC_XBRL_FACTS:
            return exists(select(1).where(SECXBRLFactObservation.company_id == Security.company_id))
        if dataset is IngestionDataset.NEWS:
            return exists(select(1).where(News.company_id == Security.company_id))
        raise ValueError(f"No persisted-row policy exists for dataset: {dataset.value}")

    def get_current_research_ready(
        self,
        *,
        required_datasets: tuple[IngestionDataset, ...],
        as_of: datetime,
    ) -> list[Security]:
        """Return active common stocks whose required datasets are fresh.

        This is deliberately a computed readiness view, not a persisted boolean.
        A security can be research-ready for one capability and not another.
        """
        stmt = select(Security).where(
            Security.status == SecurityStatus.ACTIVE,
            Security.security_type == SecurityType.COMMON_STOCK,
        )

        for dataset in required_datasets:
            policy = DATASET_POLICIES[dataset]
            cutoff = as_of - policy.max_age
            scope_company = dataset in {
                IngestionDataset.COMPANY,
                IngestionDataset.NEWS,
                IngestionDataset.INCOME_STATEMENT,
                IngestionDataset.CASH_FLOW_STATEMENT,
                IngestionDataset.BALANCE_SHEET,
                IngestionDataset.SEC_FILINGS,
                IngestionDataset.SEC_XBRL_FACTS,
            }
            state_match = and_(
                IngestionState.dataset == dataset,
                IngestionState.last_success_at.is_not(None),
                # A future ingestion timestamp must never make a historical
                # readiness check pass. This is a PIT boundary, not merely
                # a freshness-duration check.
                IngestionState.last_success_at >= cutoff,
                IngestionState.last_success_at <= as_of,
                (
                    IngestionState.company_id == Security.company_id
                    if scope_company
                    else IngestionState.security_id == Security.id
                ),
            )
            stmt = stmt.where(exists(select(1).where(state_match)))
            if policy.requires_persisted_rows:
                stmt = stmt.where(self._persisted_row_exists(dataset))

        return list(self.db.scalars(stmt.order_by(Security.symbol, Security.id)).all())

    def get_listing_universe_as_of(
        self,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> list[Security]:
        """Resolve listings known at a historical point without survivorship bias."""
        # First select the latest known revision of each effective interval.
        # Only then evaluate whether that selected revision was effective on
        # the requested date. Filtering the effective interval before revision
        # selection would allow an older open-ended row to leak into a PIT
        # universe after a later-known backdated transition.
        ranked = (
            select(
                SecurityIdentifierHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=(
                        SecurityIdentifierHistory.security_id,
                        SecurityIdentifierHistory.symbol,
                        SecurityIdentifierHistory.exchange,
                        SecurityIdentifierHistory.effective_from,
                    ),
                    order_by=(
                        SecurityIdentifierHistory.known_at.desc(),
                        SecurityIdentifierHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(SecurityIdentifierHistory.known_at <= known_at)
            .subquery()
        )
        stmt = (
            select(Security)
            .join(SecurityIdentifierHistory, SecurityIdentifierHistory.security_id == Security.id)
            .join(ranked, ranked.c.id == SecurityIdentifierHistory.id)
            .where(
                ranked.c.revision_rank == 1,
                SecurityIdentifierHistory.effective_from <= effective_on,
                (SecurityIdentifierHistory.effective_to.is_(None))
                | (SecurityIdentifierHistory.effective_to > effective_on),
            )
            .order_by(Security.symbol, Security.id)
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_common_stock_classification_as_of(
        self,
        *,
        security_ids: tuple[int, ...],
        effective_on: date,
        known_at: datetime,
    ) -> set[int]:
        if not security_ids:
            return set()
        ranked = (
            select(
                SecurityClassificationHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=(
                        SecurityClassificationHistory.security_id,
                        SecurityClassificationHistory.effective_from,
                    ),
                    order_by=(
                        SecurityClassificationHistory.known_at.desc(),
                        SecurityClassificationHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(
                SecurityClassificationHistory.security_id.in_(security_ids),
                SecurityClassificationHistory.known_at <= known_at,
            )
            .subquery()
        )
        stmt = (
            select(SecurityClassificationHistory.security_id)
            .join(ranked, ranked.c.id == SecurityClassificationHistory.id)
            .where(
                ranked.c.revision_rank == 1,
                SecurityClassificationHistory.security_type == SecurityType.COMMON_STOCK,
                SecurityClassificationHistory.effective_from <= effective_on,
                (SecurityClassificationHistory.effective_to.is_(None))
                | (SecurityClassificationHistory.effective_to > effective_on),
            )
        )
        return {int(security_id) for security_id in self.db.scalars(stmt).all()}

    def get_historical_revision_eligible(
        self,
        *,
        securities: list[Security],
        effective_on: date,
        known_at: datetime,
        financial_requirements: tuple[tuple[FinancialStatementType, FinancialPeriodType], ...],
        require_price_history: bool,
    ) -> set[int]:
        if not securities:
            return set()

        eligible = {security.id for security in securities}
        company_by_security = {security.id: security.company_id for security in securities}

        for statement_type, period_type in financial_requirements:
            matching = self.db.execute(
                select(FinancialStatementRevision.company_id)
                .where(
                    FinancialStatementRevision.company_id.in_(company_by_security.values()),
                    FinancialStatementRevision.statement_type == statement_type,
                    FinancialStatementRevision.period_type == period_type,
                    FinancialStatementRevision.fiscal_date <= effective_on,
                    FinancialStatementRevision.known_at <= known_at,
                )
                .distinct()
            ).scalars().all()
            companies = {int(company_id) for company_id in matching}
            eligible = {
                security_id
                for security_id in eligible
                if company_by_security[security_id] in companies
            }
            if not eligible:
                return set()

        if require_price_history:
            matching_prices = self.db.execute(
                select(Price.security_id)
                .join(PriceObservationRevision, PriceObservationRevision.price_id == Price.id)
                .where(
                    Price.security_id.in_(eligible),
                    PriceObservationRevision.known_at <= known_at,
                    Price.date <= effective_on,
                )
                .distinct()
            ).scalars().all()
            eligible &= {int(security_id) for security_id in matching_prices}

        return eligible

    def get_historical_pit_eligible(
        self,
        *,
        effective_on: date,
        known_at: datetime,
        financial_requirements: tuple[tuple[FinancialStatementType, FinancialPeriodType], ...],
        require_price_history: bool,
    ) -> list[Security]:
        listings = self.get_listing_universe_as_of(
            effective_on=effective_on,
            known_at=known_at,
        )
        if not listings:
            return []

        listing_ids = tuple(security.id for security in listings)
        classified_ids = self.get_common_stock_classification_as_of(
            security_ids=listing_ids,
            effective_on=effective_on,
            known_at=known_at,
        )
        candidates = [security for security in listings if security.id in classified_ids]
        eligible_ids = self.get_historical_revision_eligible(
            securities=candidates,
            effective_on=effective_on,
            known_at=known_at,
            financial_requirements=financial_requirements,
            require_price_history=require_price_history,
        )
        return [security for security in candidates if security.id in eligible_ids]
