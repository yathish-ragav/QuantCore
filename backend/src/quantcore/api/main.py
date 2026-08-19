import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from quantcore.api.errors import (
    quantcore_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from quantcore.api.router import router
from quantcore.core.exceptions import QuantCoreError


app = FastAPI(
    title="QuantCore API",
    version="1.0.0",
    description="AI-Powered Institutional Equity Research Platform",
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


app.add_exception_handler(
    QuantCoreError,
    quantcore_error_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_error_handler,
)

app.add_exception_handler(
    Exception,
    unhandled_error_handler,
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "project": "QuantCore",
        "status": "running",
        "version": "1.0.0",
    }
