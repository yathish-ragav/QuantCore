from datetime import datetime
from unittest.mock import Mock

from quantcore.repositories.news_repository import NewsRepository


def make_repository():

    db = Mock()

    repository = NewsRepository(db)

    return repository, db


def make_news():

    article = Mock()

    article.id = 1
    article.company_id = 10
    article.title = "Apple reports strong earnings"
    article.publisher = "Example News"
    article.summary = "Apple reported strong quarterly results."
    article.url = "https://example.com/apple-earnings"
    article.published_at = datetime(
        2026,
        1,
        2,
    )

    return article


def test_create_adds_article_to_database():

    repository, db = make_repository()

    article = repository.create(
        company_id=10,
        title="Apple reports strong earnings",
        publisher="Example News",
        summary="Apple reported strong quarterly results.",
        url="https://example.com/apple-earnings",
        published_at=datetime(
            2026,
            1,
            2,
        ),
    )

    assert article.company_id == 10
    assert article.title == "Apple reports strong earnings"
    assert article.publisher == "Example News"
    assert article.url == (
        "https://example.com/apple-earnings"
    )

    db.add.assert_called_once_with(article)

    # Repository must not control the transaction.
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_url_returns_existing_article():

    repository, db = make_repository()

    article = make_news()

    db.scalar.return_value = article

    result = repository.get_by_url(
        article.url
    )

    assert result == article

    db.scalar.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_url_returns_none_when_article_not_found():

    repository, db = make_repository()

    db.scalar.return_value = None

    result = repository.get_by_url(
        "https://example.com/missing"
    )

    assert result is None

    db.scalar.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_and_date_returns_article():

    repository, db = make_repository()

    article = make_news()

    db.scalar.return_value = article

    result = repository.get_by_company_and_date(
        company_id=10,
        published_at=article.published_at,
    )

    assert result == article

    db.scalar.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_and_date_returns_none_when_not_found():

    repository, db = make_repository()

    db.scalar.return_value = None

    published_at = datetime(
        2026,
        1,
        2,
    )

    result = repository.get_by_company_and_date(
        company_id=10,
        published_at=published_at,
    )

    assert result is None

    db.scalar.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_for_company_returns_articles():

    repository, db = make_repository()

    articles = [
        make_news(),
        make_news(),
    ]

    db.scalars.return_value.all.return_value = articles

    result = repository.get_for_company(
        company_id=10
    )

    assert result == articles

    db.scalars.assert_called_once()

    db.scalars.return_value.all.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_for_company_returns_empty_list():

    repository, db = make_repository()

    db.scalars.return_value.all.return_value = []

    result = repository.get_for_company(
        company_id=999
    )

    assert result == []

    db.scalars.assert_called_once()

    db.scalars.return_value.all.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()