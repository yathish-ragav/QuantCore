"""Canonical package-level QuantCore application entrypoint.

The FastAPI application is defined in ``quantcore.api.main``.
This module re-exports the same application object so that both:

    quantcore.api.main:app
    quantcore.main:app

resolve to the same canonical FastAPI application.
"""

from quantcore.api.main import app


__all__ = ["app"]