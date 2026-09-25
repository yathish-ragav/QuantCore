from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from quantcore.core.enums import SecurityType
from quantcore.core.exceptions import DataValidationError
from quantcore.models.company import Company
from quantcore.models.provenance import DataSource
from quantcore.models.security import Security, SecurityStatus
from quantcore.repositories.security_classification_history_repository import (
    SecurityClassificationHistoryRepository,
)
from quantcore.universe.providers.massive import MassiveUniverseProvider
from quantcore.universe.symbol_reconciliation import symbol_aliases


@dataclass(frozen=True)
class SecurityClassificationResult:
    eligible: int
    classified: int
    unknown: int
    unmatched: int


class SecurityClassificationService:
    """Enrich the SEC security master with provider-owned instrument types."""

    def __init__(
        self,
        db: Session,
        provider: MassiveUniverseProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or MassiveUniverseProvider()
        self.classification_history_repo = SecurityClassificationHistoryRepository(db)

    def sync(self) -> SecurityClassificationResult:
        securities = list(
            self.db.scalars(
                select(Security)
                .options(joinedload(Security.company))
                .join(Company, Company.id == Security.company_id)
                .where(Security.status == SecurityStatus.ACTIVE)
            ).all()
        )

        classifications = self.provider.fetch()
        by_identity = {}
        for item in classifications:
            key = (item.cik, item.symbol)
            existing = by_identity.get(key)
            if (
                existing is not None
                and existing.security_type is not item.security_type
            ):
                raise DataValidationError(
                    "Massive returned conflicting security types for "
                    f"{item.cik}/{item.symbol}."
                )
            by_identity[key] = item

        # Build deterministic CIK + symbol aliases for provider-specific
        # ticker formatting. A normalized alias is only usable when it maps
        # to exactly one Massive row; ambiguous aliases remain unmatched.
        by_reconciled_identity: dict[tuple[str, str], list] = {}
        for item in classifications:
            for alias in symbol_aliases(item.symbol):
                by_reconciled_identity.setdefault((item.cik, alias), []).append(item)

        def resolve(cik: str, symbol: str):
            exact = by_identity.get((cik, symbol))
            if exact is not None:
                return exact

            candidates = []
            seen = set()
            for alias in symbol_aliases(symbol):
                for item in by_reconciled_identity.get((cik, alias), []):
                    identity = (item.cik, item.symbol)
                    if identity not in seen:
                        seen.add(identity)
                        candidates.append(item)

            if len(candidates) == 1:
                return candidates[0]
            return None

        classified = 0
        unknown = 0
        unmatched = 0
        fetched_at = datetime.now(timezone.utc)

        try:
            for security in securities:
                cik = security.company.cik
                item = resolve(cik, security.symbol)
                if item is None:
                    unmatched += 1
                    continue

                if item.security_type is SecurityType.UNKNOWN:
                    unknown += 1
                    continue

                observed_at = item.observed_at or fetched_at
                self.classification_history_repo.record_observation(
                    security.id,
                    item.security_type,
                    observed_at,
                    source=DataSource.MASSIVE,
                    source_reference=item.source_reference,
                )
                security.security_type = item.security_type
                security.security_type_source = DataSource.MASSIVE
                security.security_type_fetched_at = observed_at
                security.security_type_source_reference = item.source_reference
                classified += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return SecurityClassificationResult(
            eligible=len(securities),
            classified=classified,
            unknown=unknown,
            unmatched=unmatched,
        )
