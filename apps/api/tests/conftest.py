"""Pytest fixtures: transaction-rolled-back DB sessions per test, plus a
TestClient bound to the SchoolOS app with the session dependency overridden.

Database: the Postgres URL from settings. In CI/dev the convention is a
dedicated database (schoolos_test) so tests can freely drop/create tables.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.database import get_db
from app.main import app
from app.models import Base


def _test_database_url() -> str:
    """Derive a dedicated *test* database from settings.database_url.

    pytest drops and recreates every table, so it must NEVER point at the dev
    (or prod) database. The documented dev default ``schoolos_dev`` maps to
    ``schoolos_test``; an explicitly configured URL is left alone only if it
    already looks like a test database (``_test`` suffix). Anything else is
    treated as the test target (the caller chose it deliberately).
    """
    parts = urlsplit(settings.database_url)
    dbname = parts.path.lstrip("/")
    if dbname == "schoolos_dev":
        dbname = "schoolos_test"
    elif dbname.endswith("_test") or dbname == "schoolos_test":
        pass
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
    tests can exercise the gated endpoints without going through the Lumo admin."""
    from app.models import School

    school = db.get(School, school_id)
    assert school is not None, "school must exist to enable premium"
    settings = dict(school.settings or {})
    settings["ai_enabled"] = True
    school.settings = settings
    db.flush()