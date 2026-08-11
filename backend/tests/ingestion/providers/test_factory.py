from unittest.mock import patch

import pytest

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.ingestion.providers.yahoo import YahooClient


def test_factory_returns_yahoo_provider():
    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "yahoo",
    ):
        provider = ProviderFactory.get_provider()

    assert isinstance(provider, YahooClient)


def test_factory_returns_fmp_provider():
    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "fmp",
    ):
        provider = ProviderFactory.get_provider()

    assert isinstance(provider, FMPClient)


def test_factory_is_case_insensitive():
    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "YAHOO",
    ):
        provider = ProviderFactory.get_provider()

    assert isinstance(provider, YahooClient)


def test_factory_rejects_unknown_provider():
    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "unknown",
    ):
        with pytest.raises(
            ValueError,
            match="Unknown provider: unknown",
        ):
            ProviderFactory.get_provider()