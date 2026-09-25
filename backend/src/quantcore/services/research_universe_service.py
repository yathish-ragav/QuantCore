from dataclasses import dataclass
import hashlib
import json
from datetime import date, datetime, timezone

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.core.enums import FinancialPeriodType, FinancialStatementType
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.repositories.research_universe_repository import ResearchUniverseRepository
from quantcore.services.security_listing_identity_service import (
    SecurityListingIdentityService,
)


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
        self.listing_identity_service = SecurityListingIdentityService(db)

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

    def validate_historical_symbols(
        self,
        symbols: tuple[str, ...] | list[str],
        *,
        as_ofs: tuple[datetime, ...] | list[datetime],
        financial_requirements: tuple[
            tuple[FinancialStatementType, FinancialPeriodType], ...
        ] = (
            (FinancialStatementType.INCOME, FinancialPeriodType.TTM),
            (FinancialStatementType.CASH_FLOW, FinancialPeriodType.TTM),
            (FinancialStatementType.BALANCE_SHEET, FinancialPeriodType.INSTANT),
        ),
        require_price_history: bool = True,
    ) -> None:
        """Validate requested symbols against the PIT research universe.

        Every requested symbol must be a listed, common-stock security with
        the required PIT financial and price revision coverage at every
        requested boundary.  Current security state and ingestion freshness
        are intentionally ignored.
        """
        normalized_symbols = tuple(
            symbol.strip().upper()
            for symbol in symbols
            if isinstance(symbol, str) and symbol.strip()
        )
        if len(normalized_symbols) != len(tuple(symbols)):
            raise InvalidInputError("Research symbols must be non-empty strings.")
        if len(set(normalized_symbols)) != len(normalized_symbols):
            raise InvalidInputError("Research symbols must not contain duplicates.")

        normalized_as_ofs = tuple(as_ofs)
        if not normalized_as_ofs:
            raise InvalidInputError("At least one historical as-of timestamp is required.")

        for as_of in normalized_as_ofs:
            if as_of.tzinfo is None:
                raise InvalidInputError(
                    "Historical research as_of values must be timezone-aware."
                )
            resolved = {}
            missing_listing: list[str] = []
            for symbol in normalized_symbols:
                try:
                    listing = self.listing_identity_service.resolve_as_of(
                        symbol,
                        effective_on=as_of.date(),
                        known_at=as_of,
                    )
                except ResourceNotFoundError:
                    missing_listing.append(symbol)
                    continue
                resolved[symbol] = listing.security

            if missing_listing:
                raise InvalidInputError(
                    "Historical PIT eligibility failed at "
                    f"{as_of.isoformat()}: no valid listing for "
                    + ", ".join(sorted(missing_listing))
                    + "."
                )

            securities = list(resolved.values())
            classified_ids = self.repository.get_common_stock_classification_as_of(
                security_ids=tuple(security.id for security in securities),
                effective_on=as_of.date(),
                known_at=as_of,
            )
            eligible_ids = self.repository.get_historical_revision_eligible(
                securities=securities,
                effective_on=as_of.date(),
                known_at=as_of,
                financial_requirements=financial_requirements,
                require_price_history=require_price_history,
            )
            missing = [
                symbol
                for symbol, security in resolved.items()
                if security.id not in classified_ids or security.id not in eligible_ids
            ]
            if missing:
                raise InvalidInputError(
                    "Historical PIT eligibility failed at "
                    f"{as_of.isoformat()} for: "
                    + ", ".join(sorted(missing))
                    + "."
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
