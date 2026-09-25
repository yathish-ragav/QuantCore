from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


UNAUTHENTICATED_WRITE_ROUTES = [
    ("POST", "/companies/AAPL/sync"),
    ("POST", "/income-statements/AAPL/sync"),
    ("POST", "/balance-sheets/AAPL/sync"),
    ("POST", "/cash-flow-statements/AAPL/sync"),
    ("POST", "/corporate-actions/AAPL/sync"),
    ("POST", "/news/AAPL/sync"),
    ("POST", "/sec-filings/AAPL/sync"),
    ("POST", "/macro/series/CPIAUCSL/sync"),
    ("POST", "/macro/ingestion/sync"),
]


def test_provider_triggering_write_routes_require_authentication():
    for method, path in UNAUTHENTICATED_WRITE_ROUTES:
        response = client.request(method, path)
        assert response.status_code == 401, (method, path, response.text)
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_quote_route_requires_authentication_before_provider_access():
    response = client.get("/quotes/AAPL")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
