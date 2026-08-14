from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def test_get_news_returns_articles_added():
    with patch(
        "quantcore.api.endpoints.news.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 5

        response = client.get("/news/AAPL")

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "articles_added": 5,
    }

    mock_service_class.assert_called_once()

    service.sync_news.assert_called_once_with(
        "AAPL"
    )


def test_get_news_returns_zero_when_no_articles_added():
    with patch(
        "quantcore.api.endpoints.news.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 0

        response = client.get("/news/AAPL")

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "articles_added": 0,
    }

    service.sync_news.assert_called_once_with(
        "AAPL"
    )


def test_get_news_preserves_symbol():
    with patch(
        "quantcore.api.endpoints.news.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 2

        response = client.get("/news/MSFT")

    assert response.status_code == 200

    assert response.json()["symbol"] == "MSFT"

    service.sync_news.assert_called_once_with(
        "MSFT"
    )


def test_get_news_creates_service_with_database():
    with patch(
        "quantcore.api.endpoints.news.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 3

        response = client.get("/news/GOOGL")

    assert response.status_code == 200

    mock_service_class.assert_called_once()

    service.sync_news.assert_called_once_with(
        "GOOGL"
    )