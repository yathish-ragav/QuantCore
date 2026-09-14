from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.analytics_service import AnalyticsService
from quantcore.services.balance_sheet_service import BalanceSheetService
from quantcore.services.cash_flow_statement_service import (
    CashFlowStatementService,
)
from quantcore.services.company_service import CompanyService
from quantcore.services.income_statement_service import IncomeStatementService
from quantcore.services.ingestion_orchestrator import IngestionOrchestrator
from quantcore.services.news_service import NewsService
from quantcore.services.price_service import PriceService
from quantcore.services.quote_service import QuoteService
from quantcore.services.sec_filing_service import SECFilingService
from quantcore.services.corporate_action_service import CorporateActionService
from quantcore.services.macro_ingestion_orchestrator import MacroIngestionOrchestrator
from quantcore.services.research_observation_service import ResearchObservationService
from quantcore.services.research_experiment_service import ResearchExperimentService
from quantcore.services.research_dataset_service import ResearchDatasetService
from quantcore.services.research_historical_analysis_service import ResearchHistoricalAnalysisService
from quantcore.services.research_factor_computation_service import (
    ResearchFactorComputationService,
)
from quantcore.services.research_factor_panel_service import (
    ResearchFactorPanelService,
)
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_factor_evaluation_service import (
    ResearchFactorEvaluationService,
)
from quantcore.services.research_factor_return_service import ResearchFactorReturnService
from quantcore.services.research_factor_return_methodology_service import ResearchFactorReturnMethodologyService
from quantcore.services.research_signal_service import ResearchSignalService
from quantcore.services.research_portfolio_construction_service import ResearchPortfolioConstructionService
from quantcore.services.research_portfolio_product_service import ResearchPortfolioProductService
from quantcore.services.research_portfolio_risk_service import ResearchPortfolioRiskService
from quantcore.services.research_strategy_service import ResearchStrategyService


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


def get_balance_sheet_service(
    db: DbSession,
) -> BalanceSheetService:
    return BalanceSheetService(db)

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


def get_ingestion_orchestrator(
    db: DbSession,
) -> IngestionOrchestrator:
    return IngestionOrchestrator(db)


def get_sec_filing_service(
    db: DbSession,
) -> SECFilingService:
    return SECFilingService(db)


def get_corporate_action_service(
    db: DbSession,
) -> CorporateActionService:
    return CorporateActionService(db)


def get_macro_service(
    db: DbSession,
):
    from quantcore.services.macro_service import MacroService
    return MacroService(db)


def get_macro_ingestion_orchestrator(
    db: DbSession,
) -> MacroIngestionOrchestrator:
    return MacroIngestionOrchestrator(db)


def get_research_observation_service(
    db: DbSession,
) -> ResearchObservationService:
    return ResearchObservationService(db)


def get_research_experiment_service(
    db: DbSession,
) -> ResearchExperimentService:
    return ResearchExperimentService(db)


def get_research_dataset_service(
    db: DbSession,
) -> ResearchDatasetService:
    return ResearchDatasetService(db)


def get_research_historical_analysis_service(
    db: DbSession,
) -> ResearchHistoricalAnalysisService:
    return ResearchHistoricalAnalysisService(db)


def get_research_factor_computation_service() -> ResearchFactorComputationService:
    """Return the configured research factor computation service.

    Factor definitions and calculators are application-owned registrations and
    are intentionally not persisted by this dependency. The composition root
    can replace this dependency with the production registry.
    """
    return ResearchFactorComputationService((), ())


def get_research_factor_panel_service(
    computation_service: ResearchFactorComputationService = Depends(
        get_research_factor_computation_service
    ),
) -> ResearchFactorPanelService:
    """Return the configured research factor panel service."""
    return ResearchFactorPanelService(computation_service)


def get_research_factor_cross_sectional_service() -> ResearchFactorCrossSectionalService:
    """Return the deterministic cross-sectional factor ranking service."""
    return ResearchFactorCrossSectionalService()


def get_research_factor_evaluation_service() -> ResearchFactorEvaluationService:
    """Return the deterministic factor evaluation service."""
    return ResearchFactorEvaluationService()


def get_research_signal_service() -> ResearchSignalService:
    """Return the deterministic research signal construction service."""
    return ResearchSignalService()


def get_research_strategy_service() -> ResearchStrategyService:
    """Return the deterministic research strategy validation service."""
    return ResearchStrategyService()


def get_research_portfolio_product_service(
    historical_service: ResearchHistoricalAnalysisService = Depends(
        get_research_historical_analysis_service
    ),
    panel_service: ResearchFactorPanelService = Depends(get_research_factor_panel_service),
    cross_sectional_service: ResearchFactorCrossSectionalService = Depends(
        get_research_factor_cross_sectional_service
    ),
    signal_service: ResearchSignalService = Depends(get_research_signal_service),
    strategy_service: ResearchStrategyService = Depends(get_research_strategy_service),
) -> ResearchPortfolioProductService:
    return ResearchPortfolioProductService(
        historical_service,
        panel_service,
        cross_sectional_service,
        signal_service,
        strategy_service,
        ResearchPortfolioConstructionService(),
        ResearchPortfolioRiskService(),
    )


def get_research_factor_return_service() -> ResearchFactorReturnService:
    """Return the deterministic forward-return alignment service."""
    return ResearchFactorReturnService()



def get_research_factor_return_methodology_service() -> ResearchFactorReturnMethodologyService:
    """Return the deterministic factor-return methodology service."""
    return ResearchFactorReturnMethodologyService()
