from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.repositories.news_repository import NewsRepository


class NewsService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.news_repo = NewsRepository(db)

    def get_news(self, symbol: str):

        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        security = self.security_repo.get_by_symbol(
            symbol
        )

        company = security.company if security else None

        if company is None:
            raise ValueError(
                f"{symbol} not found in database."
            )

        return self.news_repo.get_for_company(
            company.id
        )

    def sync_news(self, symbol: str):

        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        try:
            security = self.security_repo.get_by_symbol(
                symbol
            )

            company = security.company if security else None

            if company is None:
                raise ValueError(
                    f"{symbol} not found in database."
                )

            raw_articles = self.client.get_news(
                symbol
            )

            articles = (
                DataTransformer.news_articles(
                    raw_articles
                )
            )

            articles = [
                DataCleaner.clean_news(article)
                for article in articles
            ]

            if not DataValidator.validate_news_articles(
                articles
            ):
                raise ValueError(
                    f"Invalid news data for '{symbol}'."
                )

            inserted = 0

            for article in articles:

                existing = self.news_repo.get_by_url(
                    article.url
                )

                if existing:
                    continue

                self.news_repo.create(
                    company_id=company.id,
                    title=article.title,
                    publisher=article.publisher,
                    summary=article.summary,
                    url=article.url,
                    published_at=article.published_at,
                )

                inserted += 1

            self.db.commit()

            return inserted

        except Exception:
            self.db.rollback()
            raise