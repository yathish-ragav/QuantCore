from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_news_service
from quantcore.schemas.responses import (
    NewsResponse,
    NewsSyncResponse,
)
from quantcore.services.news_service import NewsService


router = APIRouter(
    prefix="/news",
    tags=["News"],
)


@router.get(
    "/{symbol}",
    response_model=list[NewsResponse],
)
def get_news(
    symbol: str,
    service: NewsService = Depends(get_news_service),
):
    normalized_symbol = symbol.strip().upper()

    articles = service.get_news(
        normalized_symbol
    )

    return [
        NewsResponse(
            title=article.title,
            publisher=article.publisher,
            summary=article.summary,
            url=article.url,
            published_at=article.published_at,
        )
        for article in articles
    ]


@router.post(
    "/{symbol}/sync",
    response_model=NewsSyncResponse,
)
def sync_news(
    symbol: str,
    service: NewsService = Depends(get_news_service),
):
    normalized_symbol = symbol.strip().upper()

    articles_added = service.sync_news(
        normalized_symbol
    )

    return NewsSyncResponse(
        symbol=normalized_symbol,
        articles_added=articles_added,
    )