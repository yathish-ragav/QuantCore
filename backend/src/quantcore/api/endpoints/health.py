from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from quantcore.core.config import settings
from quantcore.core.production_data_policy import ProductionDataPolicy
from quantcore.db.database import SessionLocal

router = APIRouter()


@router.get("/health")
def health():
    """Liveness endpoint: process is running and able to serve requests."""
    return {
        "status": "ok",
        "application": "QuantCore",
    }


@router.get("/health/live")
def health_live():
    """Explicit liveness alias for load balancers and container probes."""
    return {
        "status": "ok",
        "application": "QuantCore",
    }


@router.get("/health/ready")
def health_ready():
    """Readiness endpoint requiring a live database and valid production policy."""
    checks: dict[str, str] = {}

    try:
        ProductionDataPolicy.validate_all()
        checks["configuration"] = "ok"
    except Exception as exc:
        checks["configuration"] = "failed"
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "application": "QuantCore",
                "checks": checks,
            },
        )

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "application": "QuantCore",
                "checks": checks,
            },
        )
    finally:
        db.close()

    return {
        "status": "ready",
        "application": "QuantCore",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }
