from datetime import date, datetime

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from quantcore.core.enums import SecurityType
from quantcore.ingestion.datasets import DATASET_POLICIES, IngestionDataset
from quantcore.models.ingestion import IngestionState
from quantcore.models.provenance import DataSource
from quantcore.models.security import Security, SecurityStatus
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
