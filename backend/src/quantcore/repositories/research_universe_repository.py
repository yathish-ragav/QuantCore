from datetime import date, datetime

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from quantcore.ingestion.datasets import DATASET_POLICIES, IngestionDataset
from quantcore.models.ingestion import IngestionState
from quantcore.models.security import Security, SecurityStatus
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.core.enums import SecurityType


class ResearchUniverseRepository:
    """Database selection primitives for current and point-in-time universes."""

    def __init__(self, db: Session):
        self.db = db

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
                IngestionState.last_success_at >= cutoff,
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
        ranked = (
            select(
                SecurityIdentifierHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=SecurityIdentifierHistory.security_id,
                    order_by=(
                        SecurityIdentifierHistory.known_at.desc(),
                        SecurityIdentifierHistory.effective_from.desc(),
                        SecurityIdentifierHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(
                SecurityIdentifierHistory.effective_from <= effective_on,
                (SecurityIdentifierHistory.effective_to.is_(None))
                | (SecurityIdentifierHistory.effective_to > effective_on),
                SecurityIdentifierHistory.known_at <= known_at,
            )
            .subquery()
        )
        stmt = (
            select(Security)
            .join(SecurityIdentifierHistory, SecurityIdentifierHistory.security_id == Security.id)
            .join(ranked, ranked.c.id == SecurityIdentifierHistory.id)
            .where(ranked.c.revision_rank == 1)
            .order_by(Security.symbol, Security.id)
        )
        return list(self.db.scalars(stmt).unique().all())
