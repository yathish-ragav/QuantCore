from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Mapping

from sqlalchemy.orm import Session

from quantcore.core.enums import FinancialStatementType
from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.models.provenance import DataSource
from quantcore.repositories.corporate_action_revision_repository import (
    CorporateActionRevisionRepository,
)
from quantcore.repositories.financial_statement_revision_repository import (
    FinancialStatementRevisionRepository,
)
from quantcore.repositories.macro_repository import MacroRepository
from quantcore.repositories.price_observation_revision_repository import (
    PriceObservationRevisionRepository,
)
from quantcore.repositories.sec_xbrl_fact_repository import SECXBRLFactRepository
from quantcore.repositories.security_repository import SecurityRepository


@dataclass(frozen=True)
class PITAlignedSnapshot:
    """Cross-dataset observations selected under one knowledge boundary."""

    symbol: str
    security_id: int
    company_id: int
    as_of: datetime
    prices: tuple
    income_statements: tuple
    balance_sheets: tuple
    cash_flow_statements: tuple
    corporate_actions: tuple
    sec_xbrl_facts: tuple
    macro_observations: Mapping[str, tuple]


class PITAlignmentService:
    """Coordinate existing PIT repositories under one shared as-of boundary."""

    def __init__(self, db: Session):
        self.db = db
        self.security_repo = SecurityRepository(db)
        self.price_revision_repo = PriceObservationRevisionRepository(db)
        self.financial_revision_repo = FinancialStatementRevisionRepository(db)
        self.corporate_action_revision_repo = CorporateActionRevisionRepository(db)
        self.sec_fact_repo = SECXBRLFactRepository(db)
        self.macro_repo = MacroRepository(db)

    @staticmethod
    def _normalize_as_of(as_of: datetime) -> datetime:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        if as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")
        return as_of

    def _get_security(self, symbol: str):
        normalized = symbol.strip().upper()
        if not normalized:
            raise InvalidInputError("Symbol must not be empty.")
        security = self.security_repo.get_by_symbol(normalized)
        if security is None or security.company is None:
            raise ResourceNotFoundError(f"Security '{normalized}' not found.")
        return normalized, security

    def get_snapshot(
        self,
        symbol: str,
        *,
        as_of: datetime,
        macro_series_ids: list[str] | tuple[str, ...] = (),
    ) -> PITAlignedSnapshot:
        """Build one cross-dataset PIT snapshot without materializing new data.

        Market, financial-statement, corporate-action, and SEC observations are
        selected directly from their existing PIT/revision stores. Macro
        observations use the existing vintage-date semantics, so the timestamp
        boundary is reduced to its calendar date for macro selection.
        """
        as_of = self._normalize_as_of(as_of)
        normalized, security = self._get_security(symbol)
        company_id = security.company_id

        macro_observations: dict[str, tuple] = {}
        macro_as_of: date = as_of.date()
        for series_id in macro_series_ids:
            normalized_series_id = series_id.strip().upper()
            if not normalized_series_id:
                raise InvalidInputError("Macro series IDs must not be empty.")
            series = self.macro_repo.get_series(
                normalized_series_id,
                DataSource.FRED,
            )
            if series is None:
                raise ResourceNotFoundError(
                    f"Macro series not found: {normalized_series_id}"
                )
            macro_observations[normalized_series_id] = tuple(
                self.macro_repo.get_latest_as_of(series.id, macro_as_of)
            )

        return PITAlignedSnapshot(
            symbol=normalized,
            security_id=security.id,
            company_id=company_id,
            as_of=as_of,
            prices=tuple(
                self.price_revision_repo.get_latest_for_security_as_of(
                    security.id,
                    as_of,
                )
            ),
            income_statements=tuple(
                self.financial_revision_repo.get_latest_for_company_as_of(
                    company_id,
                    FinancialStatementType.INCOME,
                    as_of,
                )
            ),
            balance_sheets=tuple(
                self.financial_revision_repo.get_latest_for_company_as_of(
                    company_id,
                    FinancialStatementType.BALANCE_SHEET,
                    as_of,
                )
            ),
            cash_flow_statements=tuple(
                self.financial_revision_repo.get_latest_for_company_as_of(
                    company_id,
                    FinancialStatementType.CASH_FLOW,
                    as_of,
                )
            ),
            corporate_actions=tuple(
                self.corporate_action_revision_repo.get_latest_for_security_as_of(
                    security.id,
                    as_of,
                )
            ),
            sec_xbrl_facts=tuple(
                self.sec_fact_repo.get_latest_for_company_as_of_timestamp(
                    company_id,
                    as_of,
                )
            ),
            macro_observations=MappingProxyType(macro_observations),
        )
