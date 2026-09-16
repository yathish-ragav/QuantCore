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

    def get_by_accessions(
        self,
        accession_numbers: set[str] | list[str],
    ) -> dict[str, SECFiling]:
        accessions = {value for value in accession_numbers if value}
        if not accessions:
            return {}
        rows = []
        values = list(accessions)
        for start in range(0, len(values), 1000):
            rows.extend(
                self.db.scalars(
                    select(SECFiling).where(
                        SECFiling.accession_number.in_(values[start : start + 1000])
                    )
                ).all()
            )
        return {row.accession_number: row for row in rows}

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

    def get_events_by_identity(
        self,
        filing_ids: set[int] | list[int],
    ) -> set[tuple[int, FilingEventType, object]]:
        ids = {value for value in filing_ids if value is not None}
        if not ids:
            return set()
        rows = self.db.scalars(
            select(FilingEvent).where(FilingEvent.filing_id.in_(ids))
        ).all()
        return {(row.filing_id, row.event_type, row.occurred_at) for row in rows}

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
