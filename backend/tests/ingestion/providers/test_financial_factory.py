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
