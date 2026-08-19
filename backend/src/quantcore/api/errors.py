import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from quantcore.core.exceptions import QuantCoreError


def _request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    return existing or str(uuid.uuid4())


async def quantcore_error_handler(
    request: Request,
    exc: QuantCoreError,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "Request validation failed.",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


async def unhandled_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected internal error occurred.",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )
