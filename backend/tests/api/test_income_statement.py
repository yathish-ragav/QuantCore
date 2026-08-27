from datetime import date
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app
from quantcore.services.financial_statement_revision import FinancialStatementSyncResult


client = TestClient(app)


def make_statement(
    fiscal_date=date(2024, 9, 28),
    total_revenue=391035000000.0,
    gross_profit=180683000000.0,
    operating_income=123216000000.0,
    net_income=93736000000.0,
    eps=6.08,
    shares_outstanding=15408095000,
):
    statement = Mock()
    statement.period_start = None
    statement.fiscal_year = 2024
    statement.fiscal_period = "FY"
    statement.period_type = "ANNUAL"
    statement.filing_date = None
    statement.filing_form = None
    statement.accession_number = None

    statement.fiscal_date = fiscal_date
    statement.total_revenue = total_revenue
    statement.gross_profit = gross_profit
    statement.operating_income = operating_income
    statement.net_income = net_income
    statement.eps = eps
    statement.shares_outstanding = shares_outstanding

    return statement


def test_get_income_statements_returns_statements():
    statement = make_statement()

    with patch(
        "quantcore.api.dependencies.IncomeStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_income_statements.return_value = [
            statement
        ]

        response = client.get(
            "/income-statements/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == [
        {
            "fiscal_date": "2024-09-28",
            "period_start": None,
            "fiscal_year": 2024,
            "fiscal_period": "FY",
            "period_type": "ANNUAL",
            "filing_date": None,
            "filing_form": None,
            "accession_number": None,
            "total_revenue": 391035000000.0,
            "gross_profit": 180683000000.0,
            "operating_income": 123216000000.0,
            "net_income": 93736000000.0,
            "eps": 6.08,
            "shares_outstanding": 15408095000,
        }
    ]

    service.get_income_statements.assert_called_once_with(
        "AAPL",
        as_of=None,
    )

    service.sync_income_statements.assert_not_called()


def test_get_income_statements_returns_empty_list():
    with patch(
        "quantcore.api.dependencies.IncomeStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_income_statements.return_value = []

        response = client.get(
            "/income-statements/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == []


def test_get_income_statements_normalizes_lowercase_symbol():
    with patch(
        "quantcore.api.dependencies.IncomeStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_income_statements.return_value = []

        response = client.get(
            "/income-statements/aapl"
        )

    assert response.status_code == 200

    service.get_income_statements.assert_called_once_with(
        "AAPL",
        as_of=None,
    )



def test_get_income_statements_supports_as_of_query():
    with patch(
        "quantcore.api.dependencies.IncomeStatementService"
    ) as mock_service_class:

        service = Mock()
        mock_service_class.return_value = service
        service.get_income_statements.return_value = []

        response = client.get(
            "/income-statements/AAPL?as_of=2026-01-05T12:00:00Z"
        )

    assert response.status_code == 200
    service.get_income_statements.assert_called_once()
    assert service.get_income_statements.call_args.kwargs["as_of"].isoformat() == "2026-01-05T12:00:00+00:00"

def test_sync_income_statements_returns_statements_added():
    with patch(
        "quantcore.api.dependencies.IncomeStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_income_statements.return_value = FinancialStatementSyncResult(
            created=2, updated=1, unchanged=3, records_processed=6
        )

        response = client.post(
            "/income-statements/AAPL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "statements_added": 2,
        "statements_updated": 1,
        "statements_unchanged": 3,
        "records_processed": 6,
    }

    service.sync_income_statements.assert_called_once_with(
        "AAPL"
    )


def test_sync_income_statements_returns_zero_when_none_added():
    with patch(
        "quantcore.api.dependencies.IncomeStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_income_statements.return_value = FinancialStatementSyncResult(
            created=0, updated=0, unchanged=0, records_processed=0
        )

        response = client.post(
            "/income-statements/AAPL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "statements_added": 0,
        "statements_updated": 0,
        "statements_unchanged": 0,
        "records_processed": 0,
    }
