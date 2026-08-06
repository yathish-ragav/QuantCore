from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.news_repository import NewsRepository


class NewsService:
    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()
        self.company_repo = CompanyRepository(db)
        self.news_repo = NewsRepository(db)

    def sync_news(self, symbol: str):

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"{symbol} not found in database."
            )

        articles = self.client.get_news(symbol)

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

        self.news_repo.commit()

        return inserted