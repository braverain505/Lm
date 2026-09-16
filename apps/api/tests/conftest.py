"""Pytest fixtures: transaction-rolled-back DB sessions per test, plus a
TestClient bound to the Clearis app with the session dependency overridden.

Database: the Postgres URL from settings. In CI/dev the convention is a
dedicated database (clearis_test) so tests can freely drop/create tables.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import Base

# The TestClient fixture enters the app's lifespan, which runs the startup
# schema sync. Migrations here would target settings.database_url (the app's
# engine) while the suite builds its tables on the derived *_test database, so
# the sync is switched off for tests.
os.environ["AUTO_MIGRATE"] = "0"

# Every test talks to the app from the same client address, so the per-IP limits
# on register / login / password-reset (3 per hour, 5 per 15 minutes) would start
# returning 429 for the rest of the run after the first few tests. The limits are
# a deployment control rather than the behaviour under test, so they are off for
# the suite; the 429 envelope itself is covered where it is raised.
limiter.enabled = False


def _test_database_url() -> str:
    """Derive a dedicated *test* database from settings.database_url.

    pytest drops and recreates every table, so it must NEVER point at the dev
    (or prod) database. The documented dev default ``clearis_dev`` maps to
    ``clearis_test``; an explicitly configured URL is accepted only if its
    database name ends with ``_test``. Anything else raises immediately —
    a misconfigured DATABASE_URL must not wipe a real database.
    """
    parts = urlsplit(settings.database_url)
    dbname = parts.path.lstrip("/")
    if dbname == "clearis_dev":
        dbname = "clearis_test"
    if not dbname.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database {dbname!r}: the test suite "
            "drops and recreates every table. Point DATABASE_URL (or the "
            "clearis_dev default) at a database whose name ends in '_test'."
        )
    return urlunsplit(parts._replace(path=f"/{dbname}"))


TEST_DATABASE_URL = _test_database_url()

# Tests must stay hermetic and offline: never call the real LLM even when a
# Groq key is present in .env. AI generation tests then always exercise the
# deterministic template fallback (and stay fast + deterministic).
settings.groq_api_key = ""

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session")
def test_engine():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(test_engine) -> Session:
    """One transaction per test, always rolled back (never touches real data)."""
    connection = test_engine.connect()
    trans = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def client(db) -> TestClient:
    """HTTP client bound to the app with get_db overridden to the test session."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# --- Helpers ------------------------------------------------------------------
def register_school(
    client: TestClient, name: str = "Test Academy", email: str = "admin@test.edu",
    password: str = "Str0ng!Pass", school_type: str = "secondary",
) -> dict:
    """Register a school + founding admin through the API. Returns auth data
    (user, access token, memberships). Cookies are stored on the client."""
    r = client.post(
        "/api/auth/register-school",
        json={
            "school_name": name,
            "school_type": school_type,
            "admin_email": email,
            "admin_full_name": "School Admin",
            "password": password,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def active_school_id(client: TestClient) -> str:
    """The school_id of the currently logged-in client's first membership."""
    r = client.get("/api/auth/me")
    assert r.status_code == 200, r.text
    memberships = r.json()["memberships"]
    assert memberships, "expected at least one membership"
    return memberships[0]["school_id"]


def enable_premium(db, school_id: str) -> None:
    """Flip a school's premium (AI) plan on directly via the DB session, so AI
    tests can exercise the gated endpoints without going through the Clearis admin."""
    from app.models import School

    school = db.get(School, school_id)
    assert school is not None, "school must exist to enable premium"
    settings = dict(school.settings or {})
    settings["ai_enabled"] = True
    school.settings = settings
    db.flush()