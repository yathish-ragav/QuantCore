from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.news_repository import NewsRepository
from quantcore.repositories.security_repository import SecurityRepository


class NewsService:

    def __init__(self, db: Session):
        self.db = db

        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.news_repo = NewsRepository(db)

    def _get_company_for_symbol(
        self,
        symbol: str,
    ):
        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        security = self.security_repo.get_by_symbol(
            symbol
        )

        company = (
            security.company
            if security is not None
            else None
        )

        if company is None:
            raise ValueError(
                f"{symbol} not found in database."
            )

        return security, company

    def get_news(
        self,
        symbol: str,
    ):

        _, company = self._get_company_for_symbol(
            symbol
        )

        return self.news_repo.get_for_company(
            company.id
        )

    def sync_news(
        self,
        symbol: str,
    ) -> int:

        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        try:
            # -------------------------------------------------
            # 1. Resolve Company identity.
            # -------------------------------------------------
            security, company = (
                self._get_company_for_symbol(symbol)
            )

            # -------------------------------------------------
            # 2. Fetch external data.
            # -------------------------------------------------
            raw_articles = self.client.get_news(
                symbol
            )

            # -------------------------------------------------
            # 3. Transform.
            # -------------------------------------------------
            articles = (
                DataTransformer.news_articles(
                    raw_articles
                )
            )

            # -------------------------------------------------
            # 4. Clean.
            # -------------------------------------------------
            articles = [
                DataCleaner.clean_news(article)
                for article in articles
            ]

            # -------------------------------------------------
            # 5. Validate entire dataset before mutation.
            # -------------------------------------------------
            if not DataValidator.validate_news_articles(
                articles
            ):
                raise ValueError(
                    f"Invalid news data for '{symbol}'."
                )

            inserted = 0

            # -------------------------------------------------
            # 6. Reconcile articles.
            # -------------------------------------------------
            for article in articles:

                existing = self.news_repo.get_by_url(
                    article.url
                )

                if existing is not None:
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

            # -------------------------------------------------
            # 7. Commit the entire sync atomically.
            # -------------------------------------------------
            self.db.commit()

            return inserted

        except Exception:
            self.db.rollback()
            raise