from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.news_service import NewsService

router = APIRouter(prefix="/news", tags=["News"])


@router.get("/{symbol}")
def get_news(symbol: str, db: Session = Depends(get_db)):
    service = NewsService(db)

    inserted = service.sync_news(symbol)

    return {
        "symbol": symbol,
        "articles_added": inserted,
    }