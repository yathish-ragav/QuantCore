from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from quantcore.core.config import BACKEND_ROOT, settings
from quantcore.core.production_data_policy import ProductionDataPolicy
from quantcore.db.database import SessionLocal

logger = logging.getLogger(__name__)

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
    except Exception:
        checks["configuration"] = "failed"
        logger.exception(
            "Readiness configuration check failed",
            extra={"event": "health.readiness.configuration_failed"},
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "application": "QuantCore",
                "checks": checks,
                "reason": "configuration_invalid",
            },
        )

    db = SessionLocal()
    try:
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            checks["database"] = "failed"
            logger.exception(
                "Readiness database check failed",
                extra={"event": "health.readiness.database_failed"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "application": "QuantCore",
                    "checks": checks,
                    "reason": "database_unavailable",
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
            logger.exception(
                "Readiness schema check failed",
                extra={"event": "health.readiness.schema_check_failed"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "application": "QuantCore",
                    "checks": checks,
                    "reason": "schema_check_failed",
                },
            )

        if actual != expected:
            checks["schema"] = "failed"
            logger.error(
                "Readiness schema revision mismatch: expected=%s actual=%s",
                sorted(expected),
                sorted(actual),
                extra={"event": "health.readiness.schema_mismatch"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "application": "QuantCore",
                    "checks": checks,
                    "reason": "schema_revision_mismatch",
                    "expected_revisions": sorted(expected),
                    "actual_revisions": sorted(actual),
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
