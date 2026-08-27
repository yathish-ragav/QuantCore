from unittest.mock import patch

from quantcore.ingestion.providers.regulatory_factory import RegulatoryProviderFactory
from quantcore.ingestion.providers.sec import SECProvider


def test_regulatory_provider_factory_resolves_sec():
    with patch(
        "quantcore.ingestion.providers.regulatory_factory.settings.regulatory_data_provider",
        "sec",
    ):
        provider = RegulatoryProviderFactory.get_provider()

    assert isinstance(provider, SECProvider)
