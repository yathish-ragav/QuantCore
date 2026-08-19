from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def test_unknown_route_returns_fastapi_default_not_quantcore_error():
    response = client.get("/does-not-exist")

    assert response.status_code == 404


def test_request_id_is_returned_on_success():
    request_id = "quantcore-test-request"

    response = client.get(
        "/health",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
