from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.company import Company


class CompanyRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_cik(
        self,
        cik: str,
    ) -> Company | None:

        stmt = select(Company).where(
            Company.cik == cik
        )

        return self.db.scalar(stmt)

    def get_by_ciks(
        self,
        ciks: list[str],
    ) -> list[Company]:

        if not ciks:
            return []

        stmt = select(Company).where(
            Company.cik.in_(ciks)
        )

        return list(
            self.db.scalars(stmt).all()
        )

    def create(
        self,
        cik: str,
        name: str,
        sector: str,
        industry: str,
        country: str,
        website: str,
        market_cap: int | None,
    ):

        company = Company(
            cik=cik,
            name=name,
            sector=sector,
            industry=industry,
            country=country,
            website=website,
            market_cap=market_cap,
        )

        self.db.add(company)

        return company

    def update(
        self,
        company: Company,
        name: str,
        sector: str,
        industry: str,
        country: str,
        website: str,
        market_cap: int | None,
        cik: str | None = None,
    ):

        company.name = name
        company.sector = sector
        company.industry = industry
        company.country = country
        company.website = website
        company.market_cap = market_cap

        if cik is not None:
            company.cik = cik

        return company