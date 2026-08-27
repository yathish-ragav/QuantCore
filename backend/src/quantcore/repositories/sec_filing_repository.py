from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.core.enums import FilingEventType
from quantcore.models.sec_filing import FilingEvent, SECFiling


class SECFilingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_accession(
        self,
        accession_number: str,
    ) -> SECFiling | None:
        return self.db.scalar(
            select(SECFiling).where(
                SECFiling.accession_number == accession_number
            )
        )

    def get_for_company(
        self,
        company_id: int,
    ) -> list[SECFiling]:
        stmt = (
            select(SECFiling)
            .where(SECFiling.company_id == company_id)
            .order_by(
                SECFiling.filing_date.desc(),
                SECFiling.accession_number.desc(),
            )
        )
        return list(self.db.scalars(stmt).all())

    def get_events_for_company(
        self,
        company_id: int,
    ) -> list[FilingEvent]:
        stmt = (
            select(FilingEvent)
            .join(FilingEvent.filing)
            .where(SECFiling.company_id == company_id)
            .order_by(FilingEvent.occurred_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def create(self, **kwargs) -> SECFiling:
        filing = SECFiling(**kwargs)
        self.db.add(filing)
        return filing

    def get_event(
        self,
        filing_id: int,
        event_type: FilingEventType,
        occurred_at,
    ) -> FilingEvent | None:
        return self.db.scalar(
            select(FilingEvent).where(
                FilingEvent.filing_id == filing_id,
                FilingEvent.event_type == event_type,
                FilingEvent.occurred_at == occurred_at,
            )
        )

    def create_event(self, **kwargs) -> FilingEvent:
        event = FilingEvent(**kwargs)
        self.db.add(event)
        return event
