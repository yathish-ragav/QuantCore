from unittest.mock import patch

from quantcore.ingestion.providers.financial_factory import (
    FinancialProviderFactory,
)
from quantcore.ingestion.providers.fmp import FMPClient


def test_financial_factory_returns_fmp_provider():
    with patch(
        "quantcore.ingestion.providers.financial_factory.settings.financial_data_provider",
        "fmp",
    ):
        provider = FinancialProviderFactory.get_provider()

    assert isinstance(provider, FMPClient)


def test_financial_and_regulatory_factories_share_session_companyfacts_cache():
    from quantcore.ingestion.providers.regulatory_factory import RegulatoryProviderFactory

    class DummySession:
        def __init__(self):
            self.info = {}

    db = DummySession()
    with patch(
        "quantcore.ingestion.providers.financial_factory.settings.financial_data_provider",
        "sec",
    ), patch(
        "quantcore.ingestion.providers.regulatory_factory.settings.regulatory_data_provider",
        "sec",
    ):
        financial = FinancialProviderFactory.get_provider(db)
        regulatory = RegulatoryProviderFactory.get_provider(db)

    assert financial._company_facts_cache is regulatory._company_facts_cache
