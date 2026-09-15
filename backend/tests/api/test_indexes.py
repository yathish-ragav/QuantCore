from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_index():
    index = Mock()
    index.id = 1
    index.key = "SP500"
    index.name = "S&P 500"
    index.provider = "licensed-provider"
    index.methodology_reference = "methodology-ref"
    index.source_reference = "source-ref"
    index.is_active = True
    return index


def make_member():
    member = Mock()
    member.security_id = 10
    member.security.symbol = "AAPL"
    member.security.exchange = "NASDAQ"
    member.security.company_id = 100
    member.effective_from = date(2020, 1, 1)
    member.effective_to = None
    member.weight = Decimal("0.07")
    member.source_reference = "source-ref"
    member.known_at = __import__("datetime").datetime(2020, 1, 1)
    member.observed_at = __import__("datetime").datetime(2026, 1, 1)
    return member


def test_list_indexes_returns_active_index_metadata():
    with patch("quantcore.api.dependencies.MarketIndexService") as mock_service:
        service = Mock()
        service.list_active.return_value = [make_index()]
        mock_service.return_value = service

        response = client.get("/indexes")

    assert response.status_code == 200
    assert response.json()["indexes"][0]["key"] == "SP500"
    assert response.json()["indexes"][0]["provider"] == "licensed-provider"
    service.list_active.assert_called_once_with()


def test_get_index_normalizes_key():
    with patch("quantcore.api.dependencies.MarketIndexService") as mock_service:
        service = Mock()
        service.get.return_value = make_index()
        mock_service.return_value = service

        response = client.get("/indexes/sp500")

    assert response.status_code == 200
    assert response.json()["key"] == "SP500"
    service.get.assert_called_once_with("sp500")


def test_get_index_constituents_is_point_in_time():
    with patch("quantcore.api.dependencies.MarketIndexService") as mock_service:
        service = Mock()
        service.constituents_as_of.return_value = [make_member()]
        mock_service.return_value = service

        response = client.get("/indexes/SP500/constituents?as_of=2020-06-01T00:00:00Z")

    assert response.status_code == 200
    data = response.json()[0]
    assert data["security_id"] == 10
    assert data["symbol"] == "AAPL"
    assert data["effective_from"] == "2020-01-01"
    assert data["weight"] == "0.07"


def test_resolve_index_universe_returns_fingerprint_and_members():
    with patch("quantcore.api.dependencies.MarketIndexService") as mock_service:
        service = Mock()
        service.resolve.return_value = Mock(
            index_key="SP500",
            as_of=__import__("datetime").datetime(2020, 6, 1),
            security_ids=(10, 11),
            fingerprint="a" * 64,
            size=2,
        )
        mock_service.return_value = service

        response = client.get("/indexes/SP500/universe?as_of=2020-06-01T00:00:00Z")

    assert response.status_code == 200
    assert response.json() == {
        "index_key": "SP500",
        "as_of": "2020-06-01T00:00:00",
        "security_ids": [10, 11],
        "fingerprint": "a" * 64,
        "size": 2,
    }
    service.resolve.assert_called_once_with("SP500", as_of=__import__("datetime").datetime(2020, 6, 1, tzinfo=__import__("datetime").timezone.utc))
