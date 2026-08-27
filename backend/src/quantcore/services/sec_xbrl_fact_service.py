from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.ingestion.providers.regulatory_factory import RegulatoryProviderFactory
from quantcore.models.provenance import DataSource
from quantcore.models.sec_xbrl_fact import build_sec_xbrl_fact_identity_hash
from quantcore.repositories.sec_xbrl_fact_repository import SECXBRLFactRepository
from quantcore.repositories.sec_filing_repository import SECFilingRepository
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData


@dataclass(frozen=True)
class SECXBRLFactSyncResult:
    created: int
    unchanged: int
    records_processed: int


class SECXBRLFactService:
    """Persist immutable SEC XBRL observations while retaining filing revisions."""

    def __init__(self, db: Session):
        self.db = db
        self.provider = RegulatoryProviderFactory.get_provider()
        self.security_repo = SecurityRepository(db)
        self.filing_repo = SECFilingRepository(db)
        self.fact_repo = SECXBRLFactRepository(db)

    def get_company_for_symbol(self, symbol: str):
        normalized = symbol.strip().upper()
        if not normalized:
            raise InvalidInputError("Symbol must not be empty.")

        security = self.security_repo.get_by_symbol(normalized)
        company = security.company if security is not None else None
        if company is None:
            raise ResourceNotFoundError(f"Company not found: {normalized}")
        return security, company

    def get_facts(self, symbol: str):
        _, company = self.get_company_for_symbol(symbol)
        return self.fact_repo.get_for_company(company.id)

    def get_facts_as_of(self, symbol: str, as_of: date):
        _, company = self.get_company_for_symbol(symbol)
        return self.fact_repo.get_latest_for_company_as_of(company.id, as_of)

    def sync_facts(self, symbol: str) -> SECXBRLFactSyncResult:
        try:
            symbol = symbol.strip().upper()
            if not symbol:
                raise InvalidInputError("Symbol must not be empty.")

            _, company = self.get_company_for_symbol(symbol)
            raw_observations = self.provider.get_sec_xbrl_fact_observations(company.cik)
            if not isinstance(raw_observations, list):
                raise DataValidationError(f"Invalid SEC XBRL fact data for '{symbol}'.")

            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)
            created = unchanged = records_processed = 0
            filing_cache = {}

            for data in raw_observations:
                if not isinstance(data, SECXBRLFactObservationData):
                    raise DataValidationError("SEC provider returned an invalid XBRL fact object.")

                records_processed += 1
                value = data.value
                existing = self.fact_repo.get_by_identity(
                    company_id=company.id,
                    accession_number=data.accession_number,
                    taxonomy=data.taxonomy,
                    concept=data.concept,
                    unit=data.unit,
                    period_start=data.period_start,
                    period_end=data.period_end,
                    frame=data.frame,
                    qtrs=data.qtrs,
                    value=value,
                )
                if existing is not None:
                    existing.fetched_at = fetched_at
                    unchanged += 1
                    continue

                if data.accession_number not in filing_cache:
                    filing_cache[data.accession_number] = (
                        self.filing_repo.get_by_accession(data.accession_number)
                    )
                filing = filing_cache[data.accession_number]
                identity_hash = build_sec_xbrl_fact_identity_hash(
                    company_id=company.id,
                    accession_number=data.accession_number,
                    taxonomy=data.taxonomy,
                    concept=data.concept,
                    unit=data.unit,
                    period_start=data.period_start,
                    period_end=data.period_end,
                    frame=data.frame,
                    qtrs=data.qtrs,
                    value=value,
                )
                self.fact_repo.create(
                    identity_hash=identity_hash,
                    company_id=company.id,
                    filing_id=filing.id if filing is not None else None,
                    accession_number=data.accession_number,
                    taxonomy=data.taxonomy,
                    concept=data.concept,
                    unit=data.unit,
                    value=value,
                    period_start=data.period_start,
                    period_end=data.period_end,
                    filed_at=data.filed_at,
                    accepted_at=(
                        filing.acceptance_datetime
                        if filing is not None
                        else data.accepted_at
                    ),
                    form=data.form,
                    fiscal_year=data.fiscal_year,
                    fiscal_period=data.fiscal_period,
                    frame=data.frame,
                    qtrs=data.qtrs,
                    decimals=data.decimals,
                    source=source,
                    fetched_at=fetched_at,
                    source_reference=data.accession_number,
                )
                created += 1

            self.db.commit()
            return SECXBRLFactSyncResult(
                created=created,
                unchanged=unchanged,
                records_processed=records_processed,
            )
        except Exception:
            self.db.rollback()
            raise
