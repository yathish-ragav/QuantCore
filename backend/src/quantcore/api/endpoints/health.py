from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from quantcore.core.config import BACKEND_ROOT, settings
from quantcore.core.production_data_policy import ProductionDataPolicy
from quantcore.db.database import SessionLocal

router = APIRouter()


def _expected_schema_revisions() -> set[str]:
    config = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    return set(scripts.get_heads())


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
        try:
            db.execute(text("SELECT 1"))
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

        checks["database"] = "ok"

        try:
            rows = db.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()
            expected = _expected_schema_revisions()
            actual = {str(value) for value in rows}
        except Exception:
            checks["schema"] = "failed"
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "application": "QuantCore",
                    "checks": checks,
                },
            )

        if actual != expected:
            checks["schema"] = "failed"
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "application": "QuantCore",
                    "checks": checks,
                },
            )
        checks["schema"] = "ok"
    finally:
        db.close()

    return {
        "status": "ready",
        "application": "QuantCore",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }
