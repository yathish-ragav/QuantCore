from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.ingestion.providers.sec import SECProvider
from quantcore.ingestion.providers.yahoo import YahooClient
from quantcore.universe.providers.sec import SECUniverseProvider


def test_provider_source_identifiers_are_stable():
    assert YahooClient.SOURCE == "YAHOO"
    assert FMPClient.SOURCE == "FMP"
    assert SECProvider.SOURCE == "SEC"
    assert SECUniverseProvider.SOURCE == "SEC"
