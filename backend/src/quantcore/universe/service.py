from sqlalchemy.orm import Session

from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.universe.filters import filter_us_equities
from quantcore.universe.normalizer import normalize_companies
from quantcore.universe.providers.sec import SECUniverseProvider


class UniverseService:

    def __init__(self, db: Session):
        self.db = db
        self.provider = SECUniverseProvider()
        self.company_repo = CompanyRepository(db)
        self.security_repo = SecurityRepository(db)

    def sync(self) -> int:

        companies = self.provider.fetch()

        companies = normalize_companies(companies)

        companies = filter_us_equities(companies)

        if not companies:
            return 0

        synced = 0

        try:

            # -------------------------------------------------
            # 1. Load existing companies in bulk
            # -------------------------------------------------

            ciks = [
                company.cik
                for company in companies
            ]

            symbols = [
                company.symbol
                for company in companies
            ]

            existing_by_cik = {
                company.cik: company
                for company in self.company_repo.get_by_ciks(ciks)
            }

            existing_by_symbol = {
                company.symbol: company
                for company in self.company_repo.get_by_symbols(symbols)
            }

            # -------------------------------------------------
            # 2. Reconcile companies in memory
            # -------------------------------------------------

            synced_companies = []

            for company in companies:

                existing = existing_by_cik.get(
                    company.cik
                )

                if existing is None:

                    existing = existing_by_symbol.get(
                        company.symbol
                    )

                if existing:

                    existing.cik = company.cik
                    existing.symbol = company.symbol
                    existing.name = company.name
                    existing.exchange = company.exchange

                else:

                    existing = self.company_repo.create(
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

                synced_companies.append(existing)

                synced += 1

            # -------------------------------------------------
            # 3. Assign IDs to newly-created companies
            # -------------------------------------------------

            self.db.flush()

            # -------------------------------------------------
            # 4. Load all existing securities in bulk
            # -------------------------------------------------

            company_ids = [
                company.id
                for company in synced_companies
            ]

            securities = self.security_repo.get_by_company_ids(
                company_ids
            )

            existing_securities = {
                (
                    security.company_id,
                    security.symbol,
                ): security
                for security in securities
            }

            # -------------------------------------------------
            # 5. Reconcile securities in memory
            # -------------------------------------------------

            for universe_company, company in zip(
                companies,
                synced_companies,
            ):

                key = (
                    company.id,
                    universe_company.symbol,
                )

                security = existing_securities.get(key)

                if security is None:

                    security = self.security_repo.create(
                        company_id=company.id,
                        symbol=universe_company.symbol,
                        exchange=universe_company.exchange,
                    )

                else:

                    security.symbol = universe_company.symbol
                    security.exchange = universe_company.exchange

            # -------------------------------------------------
            # 6. Commit entire universe transaction
            # -------------------------------------------------

            self.db.commit()

            return synced

        except Exception:

            self.db.rollback()

            raise