from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app
from quantcore.services.sec_filing_service import SECFilingSyncResult


client = TestClient(app)


def make_filing():
    filing = Mock()
    filing.accession_number = "0000320193-24-000123"
    filing.filing_date = date(2024, 11, 1)
    filing.report_date = date(2024, 9, 28)
    filing.acceptance_datetime = datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc)
    filing.form = "10-K"
    filing.act = "34"
    filing.file_number = "001-36743"
    filing.film_number = None
    filing.items = None
    filing.primary_document = "aapl.htm"
    filing.primary_doc_description = "Annual Report"
    filing.is_xbrl = True
    filing.is_inline_xbrl = True
    filing.fiscal_year = 2024
    filing.fiscal_period = "FY"
    filing.is_amendment = False
    filing.filing_url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl.htm"
    return filing


def test_get_sec_filings():
    with patch(
        "quantcore.api.dependencies.SECFilingService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_filings.return_value = [make_filing()]

        response = client.get("/sec-filings/AAPL")

    assert response.status_code == 200
    assert response.json()[0]["accession_number"] == "0000320193-24-000123"
    assert response.json()[0]["form"] == "10-K"
    assert response.json()[0]["is_xbrl"] is True
    service.get_filings.assert_called_once_with("AAPL")


def test_get_sec_filing_events():
    with patch(
        "quantcore.api.dependencies.SECFilingService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        event = Mock()
        event.filing.accession_number = "0000320193-24-000123"
        event.event_type.value = "FILED"
        event.occurred_at = datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc)
        service.get_filing_events.return_value = [event]

        response = client.get("/sec-filings/AAPL/events")

    assert response.status_code == 200
    assert response.json() == [{
        "accession_number": "0000320193-24-000123",
        "event_type": "FILED",
        "occurred_at": "2024-11-01T16:30:00Z",
    }]


def test_sync_sec_filings():
    with patch(
        "quantcore.api.dependencies.SECFilingService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.sync_filings.return_value = SECFilingSyncResult(
            created=2,
            updated=1,
            unchanged=4,
            events_created=2,
            records_processed=7,
        )

        response = client.post("/sec-filings/AAPL/sync")

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "AAPL",
        "filings_added": 2,
        "filings_updated": 1,
        "filings_unchanged": 4,
        "filings_processed": 7,
        "events_added": 2,
    }
