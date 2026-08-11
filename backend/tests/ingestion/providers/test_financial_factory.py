from quantcore.ingestion.providers.financial_factory import (
    FinancialProviderFactory,
)
from quantcore.ingestion.providers.fmp import FMPClient


def test_financial_factory_returns_fmp_provider():
    provider = FinancialProviderFactory.get_provider()

    assert isinstance(provider, FMPClient)