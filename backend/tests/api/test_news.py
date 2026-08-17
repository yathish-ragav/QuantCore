from datetime import datetime
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_article(
    title="Apple reports strong quarterly results",
    publisher="Example News",
    summary="Apple reported strong quarterly results.",
    url="https://example.com/article-1",
    published_at=datetime(2026, 1, 2),
):
    article = Mock()

    article.title = title
    article.publisher = publisher
    article.summary = summary
    article.url = url
    article.published_at = published_at

    return article


def test_get_news_returns_articles():
    article = make_article()

    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_news.return_value = [
            article
        ]

        response = client.get(
            "/news/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == [
        {
            "title": "Apple reports strong quarterly results",
            "publisher": "Example News",
            "summary": "Apple reported strong quarterly results.",
            "url": "https://example.com/article-1",
            "published_at": "2026-01-02T00:00:00",
        }
    ]

    mock_service_class.assert_called_once()

    service.get_news.assert_called_once_with(
        "AAPL"
    )

    service.sync_news.assert_not_called()


def test_get_news_returns_multiple_articles():
    article_1 = make_article(
        url="https://example.com/article-1"
    )

    article_2 = make_article(
        title="Apple announces new product",
        publisher="Tech News",
        summary="Apple announced a new product.",
        url="https://example.com/article-2",
        published_at=datetime(2026, 1, 3),
    )

    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_news.return_value = [
            article_1,
            article_2,
        ]

        response = client.get(
            "/news/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == [
        {
            "title": "Apple reports strong quarterly results",
            "publisher": "Example News",
            "summary": "Apple reported strong quarterly results.",
            "url": "https://example.com/article-1",
            "published_at": "2026-01-02T00:00:00",
        },
        {
            "title": "Apple announces new product",
            "publisher": "Tech News",
            "summary": "Apple announced a new product.",
            "url": "https://example.com/article-2",
            "published_at": "2026-01-03T00:00:00",
        },
    ]

    service.get_news.assert_called_once_with(
        "AAPL"
    )

    service.sync_news.assert_not_called()


def test_get_news_returns_empty_list():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_news.return_value = []

        response = client.get(
            "/news/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == []

    mock_service_class.assert_called_once()

    service.get_news.assert_called_once_with(
        "AAPL"
    )

    service.sync_news.assert_not_called()


def test_get_news_preserves_symbol():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_news.return_value = []

        response = client.get(
            "/news/MSFT"
        )

    assert response.status_code == 200

    service.get_news.assert_called_once_with(
        "MSFT"
    )

    service.sync_news.assert_not_called()


def test_get_news_normalizes_lowercase_symbol():
    article = make_article()

    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_news.return_value = [
            article
        ]

        response = client.get(
            "/news/aapl"
        )

    assert response.status_code == 200

    service.get_news.assert_called_once_with(
        "AAPL"
    )

    service.sync_news.assert_not_called()


def test_get_news_normalizes_mixed_case_symbol():
    article = make_article()

    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_news.return_value = [
            article
        ]

        response = client.get(
            "/news/aApL"
        )

    assert response.status_code == 200

    service.get_news.assert_called_once_with(
        "AAPL"
    )

    service.sync_news.assert_not_called()


def test_sync_news_returns_articles_added():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 5

        response = client.post(
            "/news/AAPL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "articles_added": 5,
    }

    mock_service_class.assert_called_once()

    service.sync_news.assert_called_once_with(
        "AAPL"
    )


def test_sync_news_returns_zero_when_no_articles_added():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 0

        response = client.post(
            "/news/AAPL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "articles_added": 0,
    }

    service.sync_news.assert_called_once_with(
        "AAPL"
    )


def test_sync_news_preserves_symbol():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 2

        response = client.post(
            "/news/MSFT/sync"
        )

    assert response.status_code == 200

    assert response.json()["symbol"] == "MSFT"

    service.sync_news.assert_called_once_with(
        "MSFT"
    )


def test_sync_news_normalizes_lowercase_symbol():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 3

        response = client.post(
            "/news/aapl/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "articles_added": 3,
    }

    service.sync_news.assert_called_once_with(
        "AAPL"
    )


def test_sync_news_normalizes_mixed_case_symbol():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 3

        response = client.post(
            "/news/aApL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "articles_added": 3,
    }

    service.sync_news.assert_called_once_with(
        "AAPL"
    )


def test_sync_news_creates_service_with_database():
    with patch(
        "quantcore.api.dependencies.NewsService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_news.return_value = 3

        response = client.post(
            "/news/GOOGL/sync"
        )

    assert response.status_code == 200

    mock_service_class.assert_called_once()

    service.sync_news.assert_called_once_with(
        "GOOGL"
    )