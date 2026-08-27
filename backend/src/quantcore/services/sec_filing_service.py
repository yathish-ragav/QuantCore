from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.enums import FilingEventType
from quantcore.core.exceptions import (
    DataValidationError,
    InvalidInputError,
    ResourceNotFoundError,
)
from quantcore.ingestion.providers.regulatory_factory import (
    RegulatoryProviderFactory,
)
from quantcore.models.provenance import DataSource
from quantcore.processing.cleaner import DataCleaner
from quantcore.repositories.sec_filing_repository import SECFilingRepository
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.schemas.sec_filing import SECFilingData


@dataclass(frozen=True)
class SECFilingSyncResult:
    """Reconciliation counts produced by one SEC filing sync."""

    created: int
    updated: int
    unchanged: int
    events_created: int
    records_processed: int


class SECFilingService:
    """Synchronize SEC filing metadata without ingesting filing documents."""

    def __init__(self, db: Session):
        self.db = db
        self.provider = RegulatoryProviderFactory.get_provider()
        self.security_repo = SecurityRepository(db)
        self.filing_repo = SECFilingRepository(db)

    def get_company_for_symbol(self, symbol: str):
        symbol = DataCleaner.clean_symbol(symbol)
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        security = self.security_repo.get_by_symbol(symbol)
        company = security.company if security is not None else None
        if company is None:
            raise ResourceNotFoundError(
                f"Company not found: {symbol}"
            )
        return security, company

    def get_filings(self, symbol: str):
        _, company = self.get_company_for_symbol(symbol)
        return self.filing_repo.get_for_company(company.id)

    def get_filing_events(self, symbol: str):
        _, company = self.get_company_for_symbol(symbol)
        return self.filing_repo.get_events_for_company(company.id)

    def sync_filings(self, symbol: str):
        try:
            symbol = DataCleaner.clean_symbol(symbol)
            if not symbol:
                raise InvalidInputError("Symbol must not be empty.")

            _, company = self.get_company_for_symbol(symbol)
            raw_filings = self.provider.get_sec_filings(company.cik)

            if not isinstance(raw_filings, list):
                raise DataValidationError(
                    f"Invalid SEC filing data for '{symbol}'."
                )

            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)
            created = 0
            updated = 0
            unchanged = 0
            events_created = 0
            records_processed = 0

            for data in raw_filings:
                if not isinstance(data, SECFilingData):
                    raise DataValidationError(
                        "SEC provider returned an invalid filing object."
                    )

                accession = data.accession_number.strip()
                if not accession:
                    continue
                records_processed += 1

                existing = self.filing_repo.get_by_accession(accession)
                if existing is None:
                    filing = self.filing_repo.create(
                        company_id=company.id,
                        accession_number=accession,
                        filing_date=data.filing_date,
                        report_date=data.report_date,
                        acceptance_datetime=data.acceptance_datetime,
                        form=data.form,
                        act=data.act,
                        file_number=data.file_number,
                        film_number=data.film_number,
                        items=data.items,
                        primary_document=data.primary_document,
                        primary_doc_description=data.primary_doc_description,
                        is_xbrl=data.is_xbrl,
                        is_inline_xbrl=data.is_inline_xbrl,
                        fiscal_year=data.fiscal_year,
                        fiscal_period=data.fiscal_period,
                        is_amendment=data.is_amendment,
                        filing_url=data.filing_url,
                        source=source,
                        fetched_at=fetched_at,
                        source_reference=accession,
                    )
                    self.db.flush()
                    created += 1
                else:
                    filing = existing
                    changed = False

                    # SEC submissions are an authoritative metadata feed. Update
                    # mutable descriptive fields without changing filing identity.
                    for field in (
                        "filing_date",
                        "report_date",
                        "acceptance_datetime",
                        "form",
                        "act",
                        "file_number",
                        "film_number",
                        "items",
                        "primary_document",
                        "primary_doc_description",
                        "is_xbrl",
                        "is_inline_xbrl",
                        "fiscal_year",
                        "fiscal_period",
                        "is_amendment",
                        "filing_url",
                    ):
                        value = getattr(data, field)
                        if getattr(filing, field) != value:
                            setattr(filing, field, value)
                            changed = True
                    if filing.source != source:
                        filing.source = source
                        changed = True
                    if filing.source_reference != accession:
                        filing.source_reference = accession
                        changed = True
                    if changed:
                        updated += 1
                    else:
                        unchanged += 1
                    filing.fetched_at = fetched_at

                occurred_at = (
                    data.acceptance_datetime
                    or datetime(
                        data.filing_date.year,
                        data.filing_date.month,
                        data.filing_date.day,
                        tzinfo=timezone.utc,
                    )
                )
                event_type = (
                    FilingEventType.AMENDED
                    if data.is_amendment
                    else FilingEventType.FILED
                )

                if self.filing_repo.get_event(
                    filing.id,
                    event_type,
                    occurred_at,
                ) is None:
                    self.filing_repo.create_event(
                        filing_id=filing.id,
                        event_type=event_type,
                        occurred_at=occurred_at,
                        source=source,
                        fetched_at=fetched_at,
                        source_reference=accession,
                    )
                    events_created += 1

            self.db.commit()
            return SECFilingSyncResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                events_created=events_created,
                records_processed=records_processed,
            )

        except Exception:
            self.db.rollback()
            raise
