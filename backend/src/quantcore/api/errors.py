from fastapi import Request
from fastapi.responses import JSONResponse

from quantcore.core.exceptions import QuantCoreError


async def quantcore_error_handler(
    request: Request,
    exc: QuantCoreError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )