from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.analytics_service import AnalyticsService
from quantcore.services.cash_flow_statement_service import (
    CashFlowStatementService,
)
from quantcore.services.company_service import CompanyService
from quantcore.services.income_statement_service import IncomeStatementService
from quantcore.services.news_service import NewsService
from quantcore.services.price_service import PriceService
from quantcore.services.quote_service import QuoteService


DbSession = Annotated[Session, Depends(get_db)]


def get_company_service(
    db: DbSession,
) -> CompanyService:
    return CompanyService(db)


def get_price_service(
    db: DbSession,
) -> PriceService:
    return PriceService(db)


def get_news_service(
    db: DbSession,
) -> NewsService:
    return NewsService(db)


def get_income_statement_service(
    db: DbSession,
) -> IncomeStatementService:
    return IncomeStatementService(db)


def get_cash_flow_statement_service(
    db: DbSession,
) -> CashFlowStatementService:
    return CashFlowStatementService(db)


def get_analytics_service(
    db: DbSession,
) -> AnalyticsService:
    return AnalyticsService(db)

def get_quote_service() -> QuoteService:
    return QuoteService()
