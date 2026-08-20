"""Database engine + session factory (synchronous SQLAlchemy 2.0 over psycopg2).

FastAPI runs sync endpoints in a threadpool, which keeps the ORM layer simple and
robust while Postgres does the real work. If profiling ever shows the threadpool
becoming the bottleneck, swapping to an async engine is a contained change.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,  # Increased for production load
    max_overflow=40,  # Total: 60 concurrent connections
    pool_timeout=30,  # Wait up to 30s for a connection
    connect_args={
        "options": "-c statement_timeout=30000"  # 30s query timeout
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