from fastapi import APIRouter

from quantcore.api.endpoints.health import router as health_router
from quantcore.api.endpoints.companies import router as companies_router
from quantcore.api.endpoints.prices import router as prices_router
from quantcore.api.endpoints.news import router as news_router
from quantcore.api.endpoints.analytics import router as analytics_router
from quantcore.api.endpoints.quotes import router as quotes_router
from quantcore.api.endpoints.income_statement import (
    router as income_statement_router,
)
from quantcore.api.endpoints.balance_sheet import (
    router as balance_sheet_router,
)
from quantcore.api.endpoints.cash_flow import (
    router as cash_flow_router,
)
from quantcore.api.endpoints.ingestion import (
    router as ingestion_router,
)
from quantcore.api.endpoints.sec_filings import (
    router as sec_filings_router,
)
from quantcore.api.endpoints.corporate_actions import (
    router as corporate_actions_router,
)
from quantcore.api.endpoints.macro import router as macro_router
from quantcore.api.endpoints.research_observations import router as research_observations_router

router = APIRouter()

router.include_router(
    health_router,
    tags=["Health"],
)

router.include_router(
    companies_router,
    tags=["Companies"],
)

router.include_router(
    prices_router,
    tags=["Prices"],
)

router.include_router(
    news_router,
    tags=["News"],
)

router.include_router(
    analytics_router,
    tags=["Analytics"],
)

router.include_router(
    quotes_router,
    tags=["Quotes"],
)

router.include_router(
    income_statement_router,
    tags=["Income Statements"],
)

router.include_router(
    cash_flow_router,
    tags=["Cash Flow Statements"],
)

router.include_router(
    balance_sheet_router,
    tags=["Balance Sheets"],
)

router.include_router(
    ingestion_router,
)

router.include_router(
    sec_filings_router,
    tags=["SEC Filings"],
)

router.include_router(
    corporate_actions_router,
    tags=["Corporate Actions"],
)

router.include_router(
    macro_router,
)

router.include_router(
    research_observations_router,
    tags=["Research Observations"],
)
