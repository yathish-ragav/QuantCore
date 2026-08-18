from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_company_service
from quantcore.schemas.responses import CompanyResponse
from quantcore.services.company_service import CompanyService


router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)


def _to_company_response(
    company,
    symbol: str,
) -> CompanyResponse:
    return CompanyResponse(
        id=company.id,
        symbol=symbol,
        name=company.name,
        sector=company.sector,
        industry=company.industry,
        country=company.country,
        website=company.website,
        market_cap=company.market_cap,
    )


@router.get(
    "/{symbol}",
    response_model=CompanyResponse,
)
def get_company(
    symbol: str,
    service: CompanyService = Depends(get_company_service),
):
    normalized_symbol = symbol.strip().upper()

    company = service.get_company(
        normalized_symbol
    )

    return _to_company_response(
        company,
        normalized_symbol,
    )


@router.post(
    "/{symbol}/sync",
    response_model=CompanyResponse,
)
def sync_company(
    symbol: str,
    service: CompanyService = Depends(get_company_service),
):
    normalized_symbol = symbol.strip().upper()

    company = service.sync_company(
        normalized_symbol
    )

    return _to_company_response(
        company,
        normalized_symbol,
    )