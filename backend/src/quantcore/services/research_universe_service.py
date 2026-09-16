from dataclasses import dataclass
from datetime import date, datetime, timezone

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.repositories.research_universe_repository import ResearchUniverseRepository


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
