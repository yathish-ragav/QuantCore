from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError

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

        symbol_to_cik: dict[str, str] = {}

        for company in companies:
            existing_cik = symbol_to_cik.get(company.symbol)

            if existing_cik is not None and existing_cik != company.cik:
                raise DataValidationError(
                    f"Security symbol '{company.symbol}' "
                    f"is associated with multiple companies: "
                    f"{existing_cik} and {company.cik}."
                )

            symbol_to_cik[company.symbol] = company.cik

        synced = 0

        try:
            # -------------------------------------------------
            # 1. Group SEC records by CIK.
            #
            # One CIK = one Company.
            # Each SEC symbol becomes a Security belonging to
            # that Company.
            # -------------------------------------------------
            companies_by_cik: dict[str, list] = {}

            for company in companies:
                companies_by_cik.setdefault(
                    company.cik,
                    [],
                ).append(company)

            ciks = list(companies_by_cik.keys())

            # -------------------------------------------------
            # 2. Load existing companies by issuer identity.
            #
            # CIK is the authoritative Company identity. There is
            # deliberately no symbol fallback because symbols
            # belong to Security, not Company.
            # -------------------------------------------------
            existing_by_cik = {
                company.cik: company
                for company in self.company_repo.get_by_ciks(ciks)
            }

            synced_companies_by_cik = {}

            # -------------------------------------------------
            # 3. Reconcile Companies.
            # -------------------------------------------------
            for cik, universe_companies in companies_by_cik.items():
                representative = universe_companies[0]
                company = existing_by_cik.get(cik)

                if company is None:
                    company = self.company_repo.create(
                        cik=cik,
                        name=representative.name,
                        sector="",
                        industry="",
                        country="",
                        website="",
                        market_cap=None,
                    )
                else:
                    company.cik = cik
                    company.name = representative.name

                synced_companies_by_cik[cik] = company
                synced += len(universe_companies)

            # -------------------------------------------------
            # 4. Assign IDs to newly-created Companies.
            # -------------------------------------------------
            self.db.flush()

            # -------------------------------------------------
            # 5. Load existing Securities in bulk.
            # -------------------------------------------------
            symbols = [company.symbol for company in companies]

            existing_securities = {
                security.symbol: security
                for security in self.security_repo.get_by_symbols(symbols)
            }

            # -------------------------------------------------
            # 6. Reconcile Securities.
            #
            # Symbol belongs to Security. A Company may therefore
            # have multiple securities without duplicating Company
            # rows.
            # -------------------------------------------------
            for universe_company in companies:
                company = synced_companies_by_cik[universe_company.cik]

                security = existing_securities.get(universe_company.symbol)

                if security is None:
                    self.security_repo.create(
                        company_id=company.id,
                        symbol=universe_company.symbol,
                        exchange=universe_company.exchange,
                    )
                else:
                    if security.company_id != company.id:
                        raise DataValidationError(
                            f"Security '{universe_company.symbol}' "
                            "is already assigned to another company."
                        )

                    security.exchange = universe_company.exchange

            # -------------------------------------------------
            # 7. Commit the complete universe transaction.
            # -------------------------------------------------
            self.db.commit()

            return synced

        except Exception:
            self.db.rollback()
            raise