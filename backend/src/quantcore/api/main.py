from fastapi import FastAPI

from quantcore.api.errors import quantcore_error_handler
from quantcore.api.router import router
from quantcore.core.exceptions import QuantCoreError


app = FastAPI(
    title="QuantCore API",
    version="1.0.0",
    description="AI-Powered Institutional Equity Research Platform",
)


app.add_exception_handler(
    QuantCoreError,
    quantcore_error_handler,
)


app.include_router(router)


@app.get("/")
def root():
    return {
        "project": "QuantCore",
        "status": "running",
        "version": "1.0.0",
    }