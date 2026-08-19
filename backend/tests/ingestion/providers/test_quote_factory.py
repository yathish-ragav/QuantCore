from unittest.mock import patch

import pytest

from quantcore.core.exceptions import ConfigurationError
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.ingestion.providers.quote_factory import QuoteProviderFactory
from quantcore.ingestion.providers.quote_provider import QuoteProvider


def test_quote_factory_returns_fmp():
    with patch(
        "quantcore.ingestion.providers.quote_factory.settings.realtime_market_data_provider",
        "fmp",
    ):
        provider = QuoteProviderFactory.get_provider()

        assert isinstance(provider, FMPClient)
        assert isinstance(provider, QuoteProvider)


def test_quote_factory_rejects_unknown_provider():
    with patch(
        "quantcore.ingestion.providers.quote_factory.settings.realtime_market_data_provider",
        "unknown",
    ):
        with pytest.raises(ConfigurationError):
            QuoteProviderFactory.get_provider()
