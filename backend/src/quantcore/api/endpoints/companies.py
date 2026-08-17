from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_company_service
from quantcore.services.company_service import CompanyService


router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)


@router.get("/{symbol}")
def get_company(
    symbol: str,
    service: CompanyService = Depends(get_company_service),
):
    normalized_symbol = symbol.strip().upper()

    company = service.get_company(
        normalized_symbol
    )

    return {
        "id": company.id,
        "symbol": normalized_symbol,
        "name": company.name,
        "sector": company.sector,
        "industry": company.industry,
        "country": company.country,
        "website": company.website,
        "market_cap": company.market_cap,
    }


@router.post("/{symbol}/sync")
def sync_company(
    symbol: str,
    service: CompanyService = Depends(get_company_service),
):
    normalized_symbol = symbol.strip().upper()

    company = service.sync_company(
        normalized_symbol
    )

    return {
        "id": company.id,
        "symbol": normalized_symbol,
        "name": company.name,
        "sector": company.sector,
        "industry": company.industry,
        "country": company.country,
        "website": company.website,
        "market_cap": company.market_cap,
    }