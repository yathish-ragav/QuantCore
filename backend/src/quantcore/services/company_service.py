from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.repositories.company_repository import CompanyRepository


class CompanyService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()
        self.repo = CompanyRepository(db)

    def sync_company(self, symbol: str):

        data = self.client.get_company_info(symbol)

        existing = self.repo.get_by_symbol(symbol)

        try:

            if existing:

                company = self.repo.update(
                    company=existing,
                    name=data.name,
                    sector=data.sector,
                    industry=data.industry,
                    country=data.country,
                    website=data.website,
                    market_cap=data.market_cap,
                )

            else:

                company = self.repo.create(
                    symbol=data.symbol,
                    name=data.name,
                    sector=data.sector,
                    industry=data.industry,
                    country=data.country,
                    website=data.website,
                    market_cap=data.market_cap,
                )

            self.db.commit()
            self.db.refresh(company)

            return company

        except Exception:
            self.db.rollback()
            raise