from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.news import News


class NewsRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> News:
        article = News(**kwargs)
        self.db.add(article)
        return article

    def get_by_url(self, url: str) -> News | None:
        stmt = (
            select(News)
            .where(News.url == url)
        )

        return self.db.scalar(stmt)

    def get_by_company_and_date(
        self,
        company_id: int,
        published_at: datetime | None,
    ) -> News | None:

        stmt = (
            select(News)
            .where(
                News.company_id == company_id,
                News.published_at == published_at,
            )
        )

        return self.db.scalar(stmt)

    def commit(self):
        self.db.commit()