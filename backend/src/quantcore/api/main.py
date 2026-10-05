import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from quantcore.api.errors import (
    quantcore_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from quantcore.api.router import router
from quantcore.core.logging import configure_logging
from quantcore.core.production_data_policy import ProductionDataPolicy
from quantcore.core.exceptions import QuantCoreError


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fail closed during production startup when the source policy is invalid."""
    ProductionDataPolicy.validate_all()
    yield


app = FastAPI(
    title="QuantCore API",
    version="1.0.0",
    description="Point-in-time, reproducible quantitative equity research platform for US markets",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    candidate = request.headers.get("X-Request-ID", "").strip()
    request_id = candidate[:128] if candidate else str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.monotonic()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "HTTP request failed",
            extra={
                "event": "http.request.failed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            },
        )
        raise

    response.headers["X-Request-ID"] = request_id
    logger.info(
        "HTTP request completed",
        extra={
            "event": "http.request.completed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        },
    )
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
