"""Database engine + session factory (synchronous SQLAlchemy 2.0 over psycopg2).

FastAPI runs sync endpoints in a threadpool, which keeps the ORM layer simple and
robust while Postgres does the real work. If profiling ever shows the threadpool
becoming the bottleneck, swapping to an async engine is a contained change.
"""
from collections.abc import Iterator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

# Pool sizing is env-driven so a small Render instance doesn't open 60
# connections it doesn't need (managed Postgres plans have hard limits).
# Conservative defaults: 5 pooled + 5 overflow = ~10 connections per worker.
_pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "5"))
_pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
_statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_timeout=_pool_timeout,
    connect_args={
        "options": f"-c statement_timeout={_statement_timeout_ms}"
    },
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on error."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()