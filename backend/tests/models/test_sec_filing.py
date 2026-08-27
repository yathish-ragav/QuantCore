from datetime import date, datetime, timezone

from quantcore.core.enums import FilingEventType
from quantcore.models.sec_filing import FilingEvent, SECFiling


def test_sec_filing_model_defaults_and_identity():
    filing = SECFiling(
        company_id=1,
        accession_number="0000320193-24-000123",
        filing_date=date(2024, 11, 1),
        form="10-K",
        is_xbrl=True,
        is_inline_xbrl=True,
    )

    assert filing.company_id == 1
    assert filing.accession_number == "0000320193-24-000123"
    assert filing.form == "10-K"
    assert filing.is_amendment is None or filing.is_amendment is False


def test_filing_event_model():
    occurred_at = datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc)
    event = FilingEvent(
        filing_id=1,
        event_type=FilingEventType.FILED,
        occurred_at=occurred_at,
    )

    assert event.filing_id == 1
    assert event.event_type is FilingEventType.FILED
    assert event.occurred_at == occurred_at
