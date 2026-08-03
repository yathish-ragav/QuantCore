from quantcore.db.database import SessionLocal
from quantcore.services.company_service import CompanyService

db = SessionLocal()

service = CompanyService(db)

company = service.sync_company("AAPL")

print(company.id)
print(company.symbol)
print(company.name)
print(company.sector)