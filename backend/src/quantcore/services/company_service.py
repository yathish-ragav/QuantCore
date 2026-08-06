from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.repositories.company_repository import CompanyRepository


class CompanyService:
    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()
        self.repo = CompanyRepository(db)

    def sync_company(self, symbol: str):

        existing = self.repo.get_by_symbol(symbol)

        if existing:
            return existing

        data = self.client.get_company_info(symbol)

        return self.repo.create(
            symbol=data.symbol,
            name=data.name,
            sector=data.sector,
            industry=data.industry,
            country=data.country,
            website=data.website,
            market_cap=data.market_cap,
        )