"""SchoolOS Super Admin platform tests.

Pinned behavior:
* Every ``/api/superadmin/*`` route requires a platform admin
  (``User.is_superadmin``); a school admin gets 403 ``ERR_PERMISSION_DENIED``.
* Overview/schools/subscriptions return real aggregates over the registered
  schools (server-side, no cross-tenant leakage).
* ``update_subscription`` changes the plan + records a billing event.
* ``add_school`` provisions a tenant with an admin account; ``reset_admin``
  returns a fresh temp password once.
* Audited impersonation: enter resolves /auth/me to the school admin and blocks
  platform routes (``ERR_IMPERSONATION_ACTIVE``) until exit.
"""
import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.models import PlatformSetting, School, SchoolSubscription, SubscriptionEvent, User
from app.services.subscription_service import ensure_default_plans
from .conftest import active_school_id, register_school

SUPER = "/api/superadmin"


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


def test_school_admin_cannot_access_superadmin(client, db):
    register_school(client)
    for path, method, body in [
        ("/overview", "get", None),
        ("/schools", "get", None),
        ("/subscriptions", "get", None),
        ("/revenue", "get", None),
        ("/ai", "get", None),
        ("/users", "get", None),
        ("/engagement", "get", None),
        ("/geo", "get", None),
        ("/activity", "get", None),
        ("/health", "get", None),
        ("/issues", "get", None),
        ("/tickets", "get", None),
        ("/audit", "get", None),
        ("/settings", "get", None),
        ("/announcements", "get", None),
        ("/schools", "post", {"name": "Nope", "admin_full_name": "X", "admin_email": "x@y.z"}),
    ]:
        r = getattr(client, method)(f"{SUPER}{path}", json=body) if body else getattr(client, method)(f"{SUPER}{path}")
        assert r.status_code == 403, f"{path} should be forbidden"
        assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED", path


def test_platform_admin_overview_reflects_registered_school(client, db):
    register_school(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.get(f"{SUPER}/overview")
    assert r.status_code == 200, r.text
    kpis = r.json()["kpis"]
    assert kpis["total_schools"] == 1
    assert kpis["students"] == 0
    assert "mrr" in kpis and "arr" in kpis

    r = client.get(f"{SUPER}/schools")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] in ("trial", "pending")


def test_superadmin_filters_and_search(client, db):
    register_school(client, name="Alpha Academy", email="alpha@test.edu")
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.get(f"{SUPER}/schools?q=Alpha")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["name"] == "Alpha Academy"

    r = client.get(f"{SUPER}/schools?q=does-not-exist")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_update_subscription_changes_plan_and_records_event(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    ensure_default_plans(db)
    r = client.patch(
        f"{SUPER}/schools/{sid}/subscription",
        json={"plan_code": "professional", "status": "active"},
    )
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["subscription"]["plan_code"] == "professional"
    assert detail["subscription"]["status"] == "active"

    sub = db.scalar(select(SchoolSubscription).where(SchoolSubscription.school_id == sid))
    assert sub is not None
    events = db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.school_id == sid)).all()
    assert any(e.event_type in ("activated", "upgraded") for e in events)

    r = client.patch(
        f"{SUPER}/schools/{sid}/subscription",
        json={"plan_code": "not-a-plan"},
    )
    assert r.status_code in (400, 422)


def test_add_school_provisions_admin_and_subscription(client, db):
    admin = _create_platform_admin(db)
    _login(client, admin.email)
    ensure_default_plans(db)

    r = client.post(
        f"{SUPER}/schools",
        json={
            "name": "New Tenant",
            "school_type": "primary",
            "state": "Lagos",
            "admin_full_name": "Founder",
            "admin_email": "founder@new.ng",
            "plan_code": "starter",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["admin_email"] == "founder@new.ng"
    assert data["temp_password"], "temp password returned once"

    school = db.scalar(select(School).where(School.slug == "new-tenant"))
    assert school is not None and school.state == "Lagos"

    r = client.post("/api/auth/login", json={"email": "founder@new.ng", "password": data["temp_password"]})
    assert r.status_code == 200, r.text
    me = client.get("/api/auth/me").json()
    assert any(m["school_name"] == "New Tenant" for m in me["memberships"])


def test_reset_admin_returns_temp_password(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(f"{SUPER}/schools/{sid}/reset-admin")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == "admin@test.edu"
    assert data["temp_password"]

    r = client.post("/api/auth/login", json={"email": "admin@test.edu", "password": data["temp_password"]})
    assert r.status_code == 200, r.text


def test_impersonation_flow_blocks_platform_admin(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(f"{SUPER}/schools/{sid}/impersonate", json={})
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    # Enter impersonation: cookies now resolve to the school admin.
    r = client.post("/api/auth/impersonate/enter", json={"token": token})
    assert r.status_code == 200, r.text
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == "admin@test.edu"
    assert me["user"]["is_superadmin"] is False

    # Platform routes are blocked while impersonating.
    r = client.get(f"{SUPER}/overview")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_IMPERSONATION_ACTIVE"

    # School-scoped endpoints work as the impersonated admin.
    r = client.get("/api/academics/sessions", headers={"X-School-Id": sid})
    assert r.status_code == 200

    # Exit restores the platform admin.
    r = client.post("/api/auth/impersonate/exit")
    assert r.status_code == 200, r.text
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == admin.email
    r = client.get(f"{SUPER}/overview")
    assert r.status_code == 200, r.text


def test_support_tickets_and_notifications(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/tickets",
        json={"school_id": sid, "subject": "Help needed", "category": "technical", "severity": "high"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open"

    r = client.get(f"{SUPER}/tickets")
    assert r.status_code == 200, r.text
    assert any(t["subject"] == "Help needed" for t in r.json()["items"])

    r = client.get(f"{SUPER}/issues")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["items"], list)

    r = client.get(f"{SUPER}/notifications")
    assert r.status_code == 200, r.text

    r = client.get(f"{SUPER}/audit")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["items"], list)


def test_platform_settings_read_and_update(client, db):
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    db.add(PlatformSetting(key="platform.currency", value="USD"))
    db.flush()

    r = client.get(f"{SUPER}/settings")
    assert r.status_code == 200, r.text
    assert "platform.currency" in r.json()

    r = client.patch(f"{SUPER}/settings", json={"updates": {"platform.maintenance_mode": True}})
    assert r.status_code == 200, r.text
    assert r.json()["platform.maintenance_mode"] is True

    r = client.get(f"{SUPER}/settings")
    assert r.json()["platform.maintenance_mode"] is True
