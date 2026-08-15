from datetime import datetime
from unittest.mock import Mock

import pytest

from quantcore.schemas.news import NewsData
from quantcore.services.news_service import NewsService


def make_service():

    db = Mock()

    service = NewsService.__new__(
        NewsService
    )

    service.db = db
    service.client = Mock()
    service.company_repo = Mock()
    service.news_repo = Mock()

    return service, db


def make_company():

    company = Mock()

    company.id = 1
    company.symbol = "AAPL"

    return company


def make_article(
    url="https://example.com/article-1",
    title="Apple reports strong quarterly results",
    publisher="Example News",
    summary="Apple reported strong quarterly results.",
    published_at=datetime(2026, 1, 2),
):

    return NewsData(
        title=title,
        publisher=publisher,
        summary=summary,
        url=url,
        published_at=published_at,
    )


# ------------------------------------------------------------------
# GET NEWS
# ------------------------------------------------------------------


def test_get_news_returns_company_articles():

    service, db = make_service()

    company = make_company()

    articles = [
        Mock(),
        Mock(),
    ]

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.news_repo.get_for_company.return_value = (
        articles
    )

    result = service.get_news("AAPL")

    assert result == articles

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.news_repo.get_for_company.assert_called_once_with(
        1
    )

    service.client.get_news.assert_not_called()

    service.news_repo.commit.assert_not_called()


def test_get_news_normalizes_symbol():

    service, db = make_service()

    company = make_company()

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.news_repo.get_for_company.return_value = []

    result = service.get_news("aapl")

    assert result == []

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.news_repo.get_for_company.assert_called_once_with(
        1
    )

    service.client.get_news.assert_not_called()


def test_get_news_company_not_found():

    service, db = make_service()

    service.company_repo.get_by_symbol.return_value = (
        None
    )

    with pytest.raises(
        ValueError,
        match="AAPL not found in database.",
    ):
        service.get_news("AAPL")

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.news_repo.get_for_company.assert_not_called()

    service.client.get_news.assert_not_called()

    service.news_repo.commit.assert_not_called()


def test_get_news_empty_result():

    service, db = make_service()

    company = make_company()

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.news_repo.get_for_company.return_value = []

    result = service.get_news("AAPL")

    assert result == []

    service.news_repo.get_for_company.assert_called_once_with(
        1
    )

    service.client.get_news.assert_not_called()


# ------------------------------------------------------------------
# SYNC NEWS
# ------------------------------------------------------------------


def test_sync_news_inserts_new_articles():

    service, db = make_service()

    company = make_company()
    article = make_article()

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article
    ]

    service.news_repo.get_by_url.return_value = None

    result = service.sync_news("AAPL")

    assert result == 1

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_news.assert_called_once_with(
        "AAPL"
    )

    service.news_repo.get_by_url.assert_called_once_with(
        article.url
    )

    service.news_repo.create.assert_called_once_with(
        company_id=1,
        title=article.title,
        publisher=article.publisher,
        summary=article.summary,
        url=article.url,
        published_at=article.published_at,
    )

    service.news_repo.commit.assert_called_once()


def test_sync_news_skips_existing_articles():

    service, db = make_service()

    company = make_company()
    article = make_article()

    existing_article = Mock()

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article
    ]

    service.news_repo.get_by_url.return_value = (
        existing_article
    )

    result = service.sync_news("AAPL")

    assert result == 0

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_news.assert_called_once_with(
        "AAPL"
    )

    service.news_repo.get_by_url.assert_called_once_with(
        article.url
    )

    service.news_repo.create.assert_not_called()

    service.news_repo.commit.assert_called_once()


def test_sync_news_inserts_multiple_new_articles():

    service, db = make_service()

    company = make_company()

    article_1 = make_article(
        url="https://example.com/article-1"
    )

    article_2 = make_article(
        url="https://example.com/article-2"
    )

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article_1,
        article_2,
    ]

    service.news_repo.get_by_url.return_value = None

    result = service.sync_news("AAPL")

    assert result == 2

    assert (
        service.news_repo.get_by_url.call_count
        == 2
    )

    assert (
        service.news_repo.create.call_count
        == 2
    )

    service.news_repo.commit.assert_called_once()


def test_sync_news_inserts_only_new_articles():

    service, db = make_service()

    company = make_company()

    article_1 = make_article(
        url="https://example.com/existing"
    )

    article_2 = make_article(
        url="https://example.com/new"
    )

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article_1,
        article_2,
    ]

    existing_article = Mock()

    service.news_repo.get_by_url.side_effect = [
        existing_article,
        None,
    ]

    result = service.sync_news("AAPL")

    assert result == 1

    assert (
        service.news_repo.get_by_url.call_count
        == 2
    )

    service.news_repo.create.assert_called_once_with(
        company_id=1,
        title=article_2.title,
        publisher=article_2.publisher,
        summary=article_2.summary,
        url=article_2.url,
        published_at=article_2.published_at,
    )

    service.news_repo.commit.assert_called_once()


def test_sync_news_company_not_found():

    service, db = make_service()

    service.company_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="AAPL not found in database.",
    ):
        service.sync_news("AAPL")

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_news.assert_not_called()

    service.news_repo.get_by_url.assert_not_called()

    service.news_repo.create.assert_not_called()

    service.news_repo.commit.assert_not_called()


def test_sync_news_no_articles():

    service, db = make_service()

    company = make_company()

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = []

    result = service.sync_news("AAPL")

    assert result == 0

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.client.get_news.assert_called_once_with(
        "AAPL"
    )

    service.news_repo.get_by_url.assert_not_called()

    service.news_repo.create.assert_not_called()

    service.news_repo.commit.assert_called_once()


def test_sync_news_uses_company_id_for_insert():

    service, db = make_service()

    company = make_company()
    company.id = 42

    article = make_article()

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article
    ]

    service.news_repo.get_by_url.return_value = None

    result = service.sync_news("AAPL")

    assert result == 1

    service.news_repo.create.assert_called_once_with(
        company_id=42,
        title=article.title,
        publisher=article.publisher,
        summary=article.summary,
        url=article.url,
        published_at=article.published_at,
    )

    service.news_repo.commit.assert_called_once()


def test_sync_news_handles_news_with_no_published_at():

    service, db = make_service()

    company = make_company()

    article = make_article(
        published_at=None
    )

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article
    ]

    service.news_repo.get_by_url.return_value = None

    result = service.sync_news("AAPL")

    assert result == 1

    service.news_repo.create.assert_called_once_with(
        company_id=1,
        title=article.title,
        publisher=article.publisher,
        summary=article.summary,
        url=article.url,
        published_at=None,
    )

    service.news_repo.commit.assert_called_once()


def test_sync_news_normalizes_dictionary_articles():

    service, db = make_service()

    company = make_company()

    article = {
        "title": "Apple reports strong quarterly results",
        "publisher": "Example News",
        "summary": "Apple reported strong quarterly results.",
        "url": "https://example.com/article-1",
        "published_at": datetime(2026, 1, 2),
    }

    service.company_repo.get_by_symbol.return_value = (
        company
    )

    service.client.get_news.return_value = [
        article
    ]

    service.news_repo.get_by_url.return_value = None

    result = service.sync_news("AAPL")

    assert result == 1

    service.news_repo.create.assert_called_once_with(
        company_id=1,
        title=article["title"],
        publisher=article["publisher"],
        summary=article["summary"],
        url=article["url"],
        published_at=article["published_at"],
    )

    service.news_repo.commit.assert_called_once()