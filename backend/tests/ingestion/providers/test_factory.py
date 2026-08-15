from unittest.mock import patch

import pytest

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.ingestion.providers.yahoo import YahooClient


def test_factory_returns_yahoo_provider():

    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "yahoo",
    ):
        provider = ProviderFactory.get_provider()

    assert isinstance(provider, YahooClient)


def test_factory_is_case_insensitive():

    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "YAHOO",
    ):
        provider = ProviderFactory.get_provider()

    assert isinstance(provider, YahooClient)


def test_factory_strips_provider_name():

    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "  yahoo  ",
    ):
        provider = ProviderFactory.get_provider()

    assert isinstance(provider, YahooClient)


def test_factory_rejects_financial_provider():

    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "fmp",
    ):
        with pytest.raises(
            ValueError,
            match="Unknown market data provider: fmp",
        ):
            ProviderFactory.get_provider()


def test_factory_rejects_unknown_provider():

    with patch(
        "quantcore.ingestion.providers.factory.settings.market_data_provider",
        "unknown",
    ):
        with pytest.raises(
            ValueError,
            match="Unknown market data provider: unknown",
        ):
            ProviderFactory.get_provider()