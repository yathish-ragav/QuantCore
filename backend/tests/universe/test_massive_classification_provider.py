from datetime import datetime, timezone

import pytest

from quantcore.core.enums import SecurityType
from quantcore.core.exceptions import ConfigurationError
from quantcore.universe.providers.massive import MassiveUniverseProvider


def test_massive_classification_provider_maps_types_and_paginates(monkeypatch):
    provider = MassiveUniverseProvider(api_key="test-key", request_interval_seconds=0)
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        payload = {
            "status": "OK",
            "results": [
                {
                    "cik": "0000320193",
                    "ticker": "AAPL",
                    "type": "CS",
                },
                {
                    "cik": "0001065088",
                    "ticker": "SPY",
                    "type": "ETF",
                },
            ],
        }
        if len(calls) == 1:
            payload["next_url"] = "https://api.massive.com/v3/reference/tickers?cursor=next"
        else:
            payload["results"] = [
                {
                    "cik": "0001234567",
                    "ticker": "ZZZ",
                    "type": "UNRECOGNIZED",
                }
            ]

        class Response:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return payload

        return Response()

    monkeypatch.setattr(
        "quantcore.universe.providers.massive.requests.get",
        fake_get,
    )

    result = provider.fetch()

    assert [item.security_type for item in result] == [
        SecurityType.COMMON_STOCK,
        SecurityType.ETF,
        SecurityType.UNKNOWN,
    ]
    assert result[0].cik == "0000320193"
    assert result[0].symbol == "AAPL"
    assert result[0].source == "MASSIVE"
    assert result[0].source_reference == "MASSIVE:TICKER:AAPL:0000320193"
    assert result[0].provider_type == "CS"
    assert result[2].provider_type == "UNRECOGNIZED"
    assert result[0].observed_at.tzinfo == timezone.utc
    assert calls[0][1]["market"] == "stocks"
    assert calls[1][1] == {"apiKey": "test-key"}


def test_massive_classification_provider_retries_rate_limit(monkeypatch):
    sleeps = []
    provider = MassiveUniverseProvider(
        api_key="test-key",
        sleep_fn=sleeps.append,
        request_interval_seconds=0,
    )
    calls = []

    class Response:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code == 429:
                import requests

                raise requests.HTTPError("429 Too Many Requests")

        def json(self):
            return self._payload

    responses = [
        Response(429, headers={"Retry-After": "7"}),
        Response(200, {
            "status": "OK",
            "results": [{"cik": "0000320193", "ticker": "AAPL", "type": "CS"}],
        }),
    ]

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        return responses.pop(0)

    monkeypatch.setattr(
        "quantcore.universe.providers.massive.requests.get",
        fake_get,
    )

    result = provider.fetch()

    assert result[0].symbol == "AAPL"
    assert sleeps == [7.0]
    assert len(calls) == 2


def test_massive_classification_provider_throttles_between_pages(monkeypatch):
    sleeps = []
    now = [0.0]

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    provider = MassiveUniverseProvider(
        api_key="test-key",
        sleep_fn=sleep,
        request_interval_seconds=12.5,
        monotonic_fn=lambda: now[0],
    )
    calls = []

    class Response:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        if len(calls) == 1:
            return Response({
                "status": "OK",
                "results": [{"cik": "0000320193", "ticker": "AAPL", "type": "CS"}],
                "next_url": "https://api.massive.com/v3/reference/tickers?cursor=next",
            })
        return Response({
            "status": "OK",
            "results": [{"cik": "0000789019", "ticker": "MSFT", "type": "CS"}],
        })

    monkeypatch.setattr(
        "quantcore.universe.providers.massive.requests.get",
        fake_get,
    )

    result = provider.fetch()

    assert [item.symbol for item in result] == ["AAPL", "MSFT"]
    assert sleeps == [12.5]
    assert len(calls) == 2


def test_massive_classification_provider_requires_api_key():
    with pytest.raises(ConfigurationError, match="MASSIVE_API_KEY"):
        MassiveUniverseProvider(api_key="")


@pytest.mark.parametrize(
    ("provider_code", "expected"),
    [
        ("PFD", SecurityType.PREFERRED_STOCK),
        ("ADRP", SecurityType.ADR),
        ("ADRR", SecurityType.ADR),
        ("ADRW", SecurityType.ADR),
        ("OS", SecurityType.COMMON_STOCK),
        ("ETS", SecurityType.ETF),
        ("ETV", SecurityType.OTHER),
        ("FUND", SecurityType.OTHER),
        ("ETN", SecurityType.OTHER),
        ("GDR", SecurityType.OTHER),
        ("BOND", SecurityType.OTHER),
        ("LT", SecurityType.OTHER),
    ],
)
def test_massive_classification_provider_maps_documented_type_codes(
    provider_code,
    expected,
):
    assert MassiveUniverseProvider._security_type(provider_code) is expected
