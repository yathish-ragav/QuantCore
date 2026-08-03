from quantcore.db.database import SessionLocal
from quantcore.services.company_service import CompanyService
from quantcore.services.price_service import PriceService

db = SessionLocal()

company_service = CompanyService(db)
price_service = PriceService(db)

company_service.sync_company("AAPL")

count = price_service.sync_price_history("AAPL")

print(f"{count} price records inserted.")