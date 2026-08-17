from fastapi import FastAPI

from quantcore.api.main import app as api_app
from quantcore.main import app as package_app


def test_package_entrypoint_uses_canonical_api_application():

    assert package_app is api_app


def test_package_entrypoint_is_fastapi_application():

    assert isinstance(
        package_app,
        FastAPI,
    )


def test_canonical_application_has_root_endpoint():

    routes = package_app.openapi()["paths"]

    assert "/" in routes


def test_canonical_application_has_health_endpoint():

    routes = package_app.openapi()["paths"]

    assert "/health" in routes