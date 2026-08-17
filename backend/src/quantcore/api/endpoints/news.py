from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_news_service
from quantcore.services.news_service import NewsService


router = APIRouter(
    prefix="/news",
    tags=["News"],
)


@router.get("/{symbol}")
def get_news(
    symbol: str,
    service: NewsService = Depends(get_news_service),
):
    normalized_symbol = symbol.strip().upper()

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
    service: NewsService = Depends(get_news_service),
):
    normalized_symbol = symbol.strip().upper()

    articles_added = service.sync_news(
        normalized_symbol
    )

    return {
        "symbol": normalized_symbol,
        "articles_added": articles_added,
    }