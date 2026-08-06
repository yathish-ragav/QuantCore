from sqlalchemy.orm import Session

from quantcore.ingestion.providers.financial_factory import (
    FinancialProviderFactory,
)


class IncomeStatementService:

    def __init__(self, db: Session):

        self.db = db

        self.provider = (
            FinancialProviderFactory.get_provider()
        )