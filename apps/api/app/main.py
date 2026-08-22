"""Lumo API — FastAPI application entry point.

Routers are thin (validate -> call service -> serialize); all business logic
lives in ``app.services``. Every tenant request is scoped by the membership
resolved in ``core.deps.get_school_context`` from the ``X-School-Id`` header.
"""
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .core.errors import register_exception_handlers
from .core.database import SessionLocal
from .core.rate_limit import limiter
from .services.tenancy_service import sync_all_school_role_templates
from .routers import (
    academics,
    attendance,
    auth,
    copilot,
    dashboard,
    fees,
    imports,
    lesson_plans,
    platform,
    portal,
    question_banks,
    results,
    roles,
    schools,
    staff,
    students,
    super_admin,
    timetable,
    payroll,
    inventory,
    library,
    uploads,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate production config, reconcile existing schools' system roles
    with the current templates so policy changes (e.g. finance moving to Accountant only)
    apply to orgs provisioned before the change."""
    # Validate production configuration
    try:
        settings.validate_production_config()
        logger.info("Production configuration validated successfully")
    except ValueError as e:
        if not settings.debug:
            logger.error(f"Production configuration validation failed: {e}")
            raise
        else:
            logger.warning(f"Production validation skipped (debug mode): {e}")

    # Reconcile role templates
    try:
        db = SessionLocal()
        try:
            sync_all_school_role_templates(db)
            db.commit()
            logger.info("Role template reconciliation completed")
        finally:
            db.close()
    except Exception:  # never take the API down over role reconciliation
        logger.exception("Role template reconciliation failed")

    # Render starts Uvicorn directly and does not run the standalone seed
    # command. Keep the platform login provisioned when its password is set.
    if os.getenv("SEED_PLATFORM_PASSWORD"):
        try:
            from .seed import ensure_platform_admin

            db = SessionLocal()
            try:
                ensure_platform_admin(db)
                db.commit()
                logger.info("Platform admin account provisioned")
            finally:
                db.close()
        except Exception:
            logger.exception("Platform admin provisioning failed")
    yield


app = FastAPI(
    title="Lumo API",
    version="0.1.0",
    docs_url="/api/docs" if settings.debug else None,  # Disable docs in production
    openapi_url="/api/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Rate limiting (stub until slowapi installed)
app.state.limiter = limiter

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    # Add request ID for tracking
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Request-ID"] = request_id

    if not settings.debug:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:;"
        )

    return response

register_exception_handlers(app)

API_PREFIX = "/api"

for module in (
    auth, schools, roles, academics, staff, students, results, lesson_plans,
    question_banks, portal, copilot, imports, fees, attendance, timetable,
    payroll, inventory, library, dashboard, uploads, platform,
    super_admin,
):
    app.include_router(module.router, prefix=API_PREFIX)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Health check endpoint with database connectivity verification."""
    db = SessionLocal()
    try:
        # Test database connectivity
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"
    finally:
        db.close()

    status = "ok" if db_status == "connected" else "unhealthy"

    return {
        "status": status,
        "service": "lumo-api",
        "version": "0.1.0",
        "database": db_status,
    }


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": "Lumo API", "docs": "/api/docs", "health": "/api/health"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)