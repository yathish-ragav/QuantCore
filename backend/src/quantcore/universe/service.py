from sqlalchemy.orm import Session

from quantcore.models.company import Company
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.universe.filters import filter_us_equities
from quantcore.universe.normalizer import normalize_companies
from quantcore.universe.providers.sec import SECUniverseProvider


class UniverseService:

    def __init__(self, db: Session):
        self.db = db
        self.provider = SECUniverseProvider()
        self.company_repo = CompanyRepository(db)

    def sync(self) -> int:

        companies = self.provider.fetch()

        companies = normalize_companies(companies)

        companies = filter_us_equities(companies)

        synced = 0

        try:

            for company in companies:

                existing = self.company_repo.get_by_cik(
                    company.cik
                )

                if existing:

                    existing.symbol = company.symbol
                    existing.name = company.name
                    existing.exchange = company.exchange

                else:

                    existing_symbol = (
                        self.company_repo.get_by_symbol(
                            company.symbol
                        )
                    )

                    if existing_symbol:
                        existing_symbol.cik = company.cik
                        existing_symbol.name = company.name
                        existing_symbol.exchange = (
                            company.exchange
                        )

                    else:
                        self.company_repo.create(
                            cik=company.cik,
                            symbol=company.symbol,
                            name=company.name,
                            exchange=company.exchange,
                            sector="",
                            industry="",
                            country="",
                            website="",
                            market_cap=None,
                        )

                synced += 1

            self.db.commit()

            return synced

        except Exception:
            self.db.rollback()
            raise