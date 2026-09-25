from dataclasses import dataclass
import hashlib
import json
from datetime import date, datetime, timezone

from quantcore.core.exceptions import InvalidInputError
from quantcore.core.enums import FinancialPeriodType, FinancialStatementType
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.repositories.research_universe_repository import ResearchUniverseRepository


@dataclass(frozen=True)
class ResearchCohort:
    """Deterministic current cohort used for controlled production validation."""

    security_ids: tuple[int, ...]
    symbols: tuple[str, ...]
    fingerprint: str
    selection: str

    @property
    def size(self) -> int:
        return len(self.security_ids)


@dataclass(frozen=True)
class ResearchUniverse:
    """Resolved security universe with explicit provenance semantics."""

    security_ids: tuple[int, ...]
    as_of: datetime
    selection: str

    @property
    def size(self) -> int:
        return len(self.security_ids)


class ResearchUniverseService:
    """Resolve research universes without conflating identity and readiness."""

    def __init__(self, db):
        self.repository = ResearchUniverseRepository(db)

    def current_common_stock_cohort(self, *, size: int) -> ResearchCohort:
        """Select a deterministic current cohort of classified common stocks.

        This is intentionally separate from research readiness: the cohort is
        used to bootstrap and benchmark data population before all required
        datasets have been ingested. Membership requires a provider-owned
        common-stock classification and an active security listing.
        """
        if size <= 0:
            raise InvalidInputError("Research cohort size must be greater than zero.")

        securities = self.repository.get_current_common_stock_cohort(size=size)
        if len(securities) != size:
            raise InvalidInputError(
                f"Requested research cohort of {size}, but only "
                f"{len(securities)} currently classified common stocks are available. "
                "Run the security classification sync and resolve unmatched/unknown "
                "securities before increasing the cohort."
            )

        members = tuple(
            (security.id, security.symbol, security.exchange)
            for security in securities
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                members,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        return ResearchCohort(
            security_ids=tuple(member[0] for member in members),
            symbols=tuple(member[1] for member in members),
            fingerprint=fingerprint,
            selection="CURRENT_CLASSIFIED_COMMON_STOCK_COHORT",
        )

    def current_ready(
        self,
        *,
        required_datasets: tuple[IngestionDataset, ...] = (IngestionDataset.PRICE_HISTORY,),
        as_of: datetime | None = None,
    ) -> ResearchUniverse:
        if as_of is None:
            as_of = datetime.now(timezone.utc)
        if as_of.tzinfo is None:
            raise InvalidInputError("Research universe as_of must be timezone-aware.")
        securities = self.repository.get_current_research_ready(
            required_datasets=required_datasets,
            as_of=as_of,
        )
        return ResearchUniverse(
            security_ids=tuple(security.id for security in securities),
            as_of=as_of,
            selection="CURRENT_RESEARCH_READY",
        )


    def historical_pit_eligible(
        self,
        *,
        effective_on: date,
        known_at: datetime,
        financial_requirements: tuple[tuple[FinancialStatementType, FinancialPeriodType], ...] = (
            (FinancialStatementType.INCOME, FinancialPeriodType.TTM),
            (FinancialStatementType.CASH_FLOW, FinancialPeriodType.TTM),
            (FinancialStatementType.BALANCE_SHEET, FinancialPeriodType.INSTANT),
        ),
        require_price_history: bool = True,
    ) -> ResearchUniverse:
        """Resolve a historical common-stock universe using only PIT evidence.

        This path deliberately ignores current ``Security.status``, current
        ``Security.security_type`` and ``IngestionState``. Eligibility is the
        intersection of PIT listing identity, bitemporal classification, and
        actual revision-store coverage for the requested research capability.
        """
        if known_at.tzinfo is None:
            raise InvalidInputError("Research universe known_at must be timezone-aware.")
        if not isinstance(effective_on, date):
            raise InvalidInputError("Research universe effective_on must be a date.")
        securities = self.repository.get_historical_pit_eligible(
            effective_on=effective_on,
            known_at=known_at,
            financial_requirements=financial_requirements,
            require_price_history=require_price_history,
        )
        return ResearchUniverse(
            security_ids=tuple(security.id for security in securities),
            as_of=known_at,
            selection="HISTORICAL_PIT_ELIGIBLE",
        )

    def listings_as_of(
        self,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> ResearchUniverse:
        if known_at.tzinfo is None:
            raise InvalidInputError("Research universe known_at must be timezone-aware.")
        securities = self.repository.get_listing_universe_as_of(
            effective_on=effective_on,
            known_at=known_at,
        )
        return ResearchUniverse(
            security_ids=tuple(security.id for security in securities),
            as_of=known_at,
            selection="LISTINGS_AS_OF",
        )
