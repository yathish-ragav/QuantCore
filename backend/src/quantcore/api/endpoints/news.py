from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.news_service import NewsService


router = APIRouter(
    prefix="/news",
    tags=["News"],
)


@router.get("/{symbol}")
def get_news(
    symbol: str,
    db: Session = Depends(get_db),
):
    normalized_symbol = symbol.strip().upper()

    service = NewsService(db)

    articles = service.get_news(
        normalized_symbol
    )

    return [
        {
            "title": article.title,
            "publisher": article.publisher,
            "summary": article.summary,
            "url": article.url,
            "published_at": article.published_at,
        }
        for article in articles
    ]


@router.post("/{symbol}/sync")
def sync_news(
    symbol: str,
    db: Session = Depends(get_db),
):
    normalized_symbol = symbol.strip().upper()

    service = NewsService(db)

    articles_added = service.sync_news(
        normalized_symbol
    )

    return {
        "symbol": normalized_symbol,
        "articles_added": articles_added,
    }