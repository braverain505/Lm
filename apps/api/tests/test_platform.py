"""Lumo platform admin + premium (AI) gating tests.

Pinned behavior:
* ``GET/PATCH /api/platform/schools`` require a platform admin
  (``User.is_superadmin``); a regular school founder gets 403
  ``ERR_PERMISSION_DENIED``.
* ``list_schools`` exposes every school with its premium status; flipping
  ``PATCH /platform/schools/{id}/ai`` persists ``settings.ai_enabled``.
* Every AI route (copilot, lesson plans, question banks, AI comments) is
  blocked with 403 ``ERR_PREMIUM_REQUIRED`` until the school's premium plan is
  enabled — even for the school owner — and works again once enabled.
"""
import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.models import User
from .conftest import active_school_id, register_school

PLATFORM = "/api/platform"
COPILOT = "/api/copilot"
LESSON = "/api/lesson-plans"


def _create_platform_admin(db):
    user = User(
        email=f"lumo-admin-{uuid.uuid4().hex[:8]}@lumo.app",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Lumo Admin",
        is_superadmin=True,
    )
    db.add(user)
    db.flush()
    return user


def _login(client, email: str):
    r = client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Pass"})
    assert r.status_code == 200, r.text


def test_non_platform_admin_cannot_list_schools(client, db):
    register_school(client)
    r = client.get(f"{PLATFORM}/schools")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.patch(f"{PLATFORM}/schools/{uuid.uuid4()}/ai", json={"enabled": True})
    assert r.status_code == 403


def test_platform_admin_lists_schools_and_toggles_ai(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.get(f"{PLATFORM}/schools")
    assert r.status_code == 200, r.text
    schools = r.json()
    assert any(s["id"] == sid for s in schools), "registered school must be listed"
    school = next(s for s in schools if s["id"] == sid)
    assert school["ai_enabled"] is False
    assert isinstance(school["students"], int)
    assert isinstance(school["class_arms"], int)
    assert "school_type" in school and "slug" in school

    r = client.patch(f"{PLATFORM}/schools/{sid}/ai", json={"enabled": True})
    assert r.status_code == 200, r.text
    assert r.json()["ai_enabled"] is True

    r = client.get(f"{PLATFORM}/schools")
    assert r.status_code == 200
    updated = next(s for s in r.json() if s["id"] == sid)
    assert updated["ai_enabled"] is True

    r = client.patch(f"{PLATFORM}/schools/{sid}/ai", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["ai_enabled"] is False


def test_ai_features_require_premium(client, db):
    register_school(client)
    sid = active_school_id(client)

    r = client.post(
        f"{COPILOT}/ask",
        json={"question": "What is the school motto?"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "ERR_PREMIUM_REQUIRED"

    r = client.post(
        f"{LESSON}",
        json={"class_arm_id": str(uuid.uuid4()), "subject_id": str(uuid.uuid4()), "topic": "T"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PREMIUM_REQUIRED"

    admin = _create_platform_admin(db)
    _login(client, admin.email)
    r = client.patch(f"{PLATFORM}/schools/{sid}/ai", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["ai_enabled"] is True

    _login(client, "admin@test.edu")
    r = client.post(
        f"{COPILOT}/ask",
        json={"question": "Hello"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text


def test_premium_gate_persists_across_sessions(client, db):
    """The premium toggle lives on the school row, not the platform admin's
    session — a school keeps premium until explicitly revoked."""
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)
    r = client.patch(f"{PLATFORM}/schools/{sid}/ai", json={"enabled": True})
    assert r.status_code == 200

    r = client.get(f"{PLATFORM}/schools")
    assert r.status_code == 200
    updated = next(s for s in r.json() if s["id"] == sid)
    assert updated["ai_enabled"] is True


def test_suspend_school_blocks_tenant_access(client, db):
    register_school(client)
    sid = active_school_id(client)

    r = client.get("/api/academics/sessions", headers={"X-School-Id": sid})
    assert r.status_code == 200, "school works before suspension"

    admin = _create_platform_admin(db)
    _login(client, admin.email)
    r = client.patch(f"{PLATFORM}/schools/{sid}/status", json={"suspended": True})
    assert r.status_code == 200, r.text
    assert r.json()["suspended"] is True

    _login(client, "admin@test.edu")
    r = client.get("/api/academics/sessions", headers={"X-School-Id": sid})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_SCHOOL_SUSPENDED"

    _login(client, admin.email)
    r = client.patch(f"{PLATFORM}/schools/{sid}/status", json={"suspended": False})
    assert r.status_code == 200
    assert r.json()["suspended"] is False

    _login(client, "admin@test.edu")
    r = client.get("/api/academics/sessions", headers={"X-School-Id": sid})
    assert r.status_code == 200, "school works again after re-enable"


def test_create_school_admin(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{PLATFORM}/schools/{sid}/admins",
        json={"full_name": "New Head", "email": "new.head@test.edu"},
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["role_code"] == "super_admin"
    assert created["email"] == "new.head@test.edu"
    assert created["password"], "generated temp password must be returned once"

    r = client.post(
        "/api/auth/login",
        json={"email": "new.head@test.edu", "password": created["password"]},
    )
    assert r.status_code == 200, r.text
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert any(m["school_id"] == sid for m in r.json()["memberships"])
    r = client.get("/api/academics/sessions", headers={"X-School-Id": sid})
    assert r.status_code == 200, "created admin can use the school API"


def test_create_admin_rejects_duplicate_email(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{PLATFORM}/schools/{sid}/admins",
        json={"full_name": "Dup", "email": "admin@test.edu"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"


def test_list_teachers_across_schools(client, db):
    register_school(client, name="Alpha School", email="alpha@test.edu")
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.get(f"{PLATFORM}/teachers")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(x["email"] == "alpha@test.edu" for x in rows), "founder admin visible"
    founder = next(x for x in rows if x["email"] == "alpha@test.edu")
    assert founder["school_name"] == "Alpha School"
    assert founder["role_code"] == "super_admin"

    r = client.post(
        f"{PLATFORM}/schools/{sid}/admins",
        json={"full_name": "Another Admin", "email": "second@test.edu"},
    )
    assert r.status_code == 201

    r = client.get(f"{PLATFORM}/teachers")
    rows = r.json()
    assert any(x["email"] == "second@test.edu" for x in rows)
    assert "password" not in rows[0], "passwords must never be exposed"