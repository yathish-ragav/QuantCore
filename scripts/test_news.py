from quantcore.db.database import SessionLocal
from quantcore.services.news_service import NewsService

db = SessionLocal()

service = NewsService(db)

count = service.sync_news("AAPL")

print(f"{count} news articles inserted.")