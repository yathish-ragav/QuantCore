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
            # 1. Group SEC records by CIK
            #
            # One CIK = one Company
            # Multiple symbols = multiple Securities
            # -------------------------------------------------

            companies_by_cik: dict[
                str,
                list
            ] = {}

            for company in companies:
                companies_by_cik.setdefault(
                    company.cik,
                    [],
                ).append(company)

            ciks = list(companies_by_cik.keys())

            symbols = [
                company.symbol
                for company in companies
            ]

            # -------------------------------------------------
            # 2. Load existing companies in bulk
            # -------------------------------------------------

            existing_by_cik = {
                company.cik: company
                for company in self.company_repo.get_by_ciks(
                    ciks
                )
            }

            existing_by_symbol = {
                company.symbol: company
                for company in self.company_repo.get_by_symbols(
                    symbols
                )
            }

            # -------------------------------------------------
            # 3. Reconcile companies
            #
            # Only one Company is created per CIK.
            # -------------------------------------------------

            synced_companies_by_cik = {}

            for cik, universe_companies in (
                companies_by_cik.items()
            ):

                representative = universe_companies[0]

                existing = existing_by_cik.get(cik)

                # Fallback to symbol if CIK does not match.
                if existing is None:

                    for universe_company in (
                        universe_companies
                    ):
                        existing = existing_by_symbol.get(
                            universe_company.symbol
                        )

                        if existing is not None:
                            break

                if existing:

                    existing.cik = cik
                    existing.symbol = representative.symbol
                    existing.name = representative.name
                    existing.exchange = representative.exchange

                else:

                    existing = self.company_repo.create(
                        cik=cik,
                        symbol=representative.symbol,
                        name=representative.name,
                        exchange=representative.exchange,
                        sector="",
                        industry="",
                        country="",
                        website="",
                        market_cap=None,
                    )

                synced_companies_by_cik[cik] = existing

                synced += len(universe_companies)

            # -------------------------------------------------
            # 4. Assign IDs to newly-created companies
            # -------------------------------------------------

            self.db.flush()

            # -------------------------------------------------
            # 5. Load existing securities in bulk
            # -------------------------------------------------

            company_ids = [
                company.id
                for company in synced_companies_by_cik.values()
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
            # 6. Reconcile securities
            # -------------------------------------------------

            for universe_company in companies:

                company = synced_companies_by_cik[
                    universe_company.cik
                ]

                key = (
                    company.id,
                    universe_company.symbol,
                )

                security = existing_securities.get(key)

                if security is None:

                    self.security_repo.create(
                        company_id=company.id,
                        symbol=universe_company.symbol,
                        exchange=universe_company.exchange,
                    )

                else:

                    security.symbol = universe_company.symbol
                    security.exchange = universe_company.exchange

            # -------------------------------------------------
            # 7. Commit entire universe transaction
            # -------------------------------------------------

            self.db.commit()

            return synced

        except Exception:

            self.db.rollback()

            raise