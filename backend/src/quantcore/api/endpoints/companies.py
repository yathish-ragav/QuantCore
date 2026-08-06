from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.company_service import CompanyService

router = APIRouter(
    prefix="/companies",
)


@router.get("/{symbol}")
def get_company(
    symbol: str,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    company = service.sync_company(
        symbol.upper()
    )

    return {
        "id": company.id,
        "symbol": company.symbol,
        "name": company.name,
        "sector": company.sector,
        "industry": company.industry,
        "country": company.country,
        "website": company.website,
        "market_cap": company.market_cap,
    }