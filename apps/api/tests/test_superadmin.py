"""Clearis Super Admin platform tests.

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
from app.models import (
    AcademicSession,
    ClassArm,
    PlatformSetting,
    School,
    SchoolSubscription,
    Student,
    StudentEnrollment,
    SubscriptionEvent,
    User,
)
from app.services.subscription_service import ensure_default_plans
from .conftest import active_school_id, register_school

SUPER = "/api/superadmin"


def _create_platform_admin(db):
    user = User(
        email=f"clearis-admin-{uuid.uuid4().hex[:8]}@clearis.site",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Clearis Admin",
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
    sid = active_school_id(client)
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
        (f"/schools/{sid}/classes", "get", None),
        (f"/schools/{sid}/classes", "post", {"name": "JSS 1A"}),
        (
            f"/schools/{sid}/students/bulk",
            "post",
            {"rows": [{"full_name": "Ada Obi", "class_arm_id": str(uuid.uuid4())}]},
        ),
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


# --- Bulk student intake ----------------------------------------------------

def _add_session_arms(db, school_id, name="2025/2026", arms=("JSS 1A", "JSS 1B"), is_current=True):
    session = AcademicSession(school_id=school_id, name=name, is_current=is_current)
    db.add(session)
    db.flush()
    created = []
    for arm_name in arms:
        arm = ClassArm(
            school_id=school_id,
            academic_session_id=session.id,
            name=arm_name,
            full_name=arm_name,
        )
        db.add(arm)
        created.append(arm)
    db.flush()
    return session, created


def test_bulk_add_students_creates_and_enrolls(client, db):
    register_school(client)
    sid = active_school_id(client)
    school_uuid = uuid.UUID(sid)
    session, arms = _add_session_arms(db, school_uuid)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.get(f"{SUPER}/schools/{sid}/classes")
    assert r.status_code == 200, r.text
    classes = r.json()
    assert classes["school"]["name"] == "Test Academy"
    assert [s["name"] for s in classes["sessions"]] == [session.name]
    assert classes["sessions"][0]["is_current"] is True
    assert len(classes["sessions"][0]["arms"]) == 2

    r = client.post(
        f"{SUPER}/schools/{sid}/students/bulk",
        json={
            "rows": [
                {
                    "full_name": "Adaeze Ngozi Okafor",
                    "class_arm_id": str(arms[0].id),
                    "gender": "female",
                },
                {"full_name": "Tunde Bakare", "class_arm_id": str(arms[1].id)},
            ]
        },
    )
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["created"] == 2 and result["failed"] == 0
    assert {s["class_arm_name"] for s in result["students"]} == {"JSS 1A", "JSS 1B"}

    students = db.scalars(
        select(Student).where(Student.school_id == school_uuid)
    ).all()
    assert len(students) == 2
    assert all(s.admission_no for s in students)
    adaeze = next(s for s in students if s.first_name == "Adaeze")
    assert (adaeze.middle_name, adaeze.last_name) == ("Ngozi", "Okafor")
    assert adaeze.gender == "female"

    enrollments = db.scalars(
        select(StudentEnrollment).where(StudentEnrollment.school_id == school_uuid)
    ).all()
    assert len(enrollments) == 2
    assert {e.class_arm_id for e in enrollments} == {arms[0].id, arms[1].id}
    assert all(e.is_current and e.status == "active" for e in enrollments)


def test_bulk_add_students_uses_the_requested_session(client, db):
    register_school(client)
    sid = active_school_id(client)
    school_uuid = uuid.UUID(sid)
    _current_session, _current_arms = _add_session_arms(
        db, school_uuid, name="2026/2027", arms=("JSS 2A",), is_current=True
    )
    previous_session, previous_arms = _add_session_arms(
        db, school_uuid, name="2025/2026", arms=("JSS 1A",), is_current=False
    )
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/students/bulk",
        json={
            "session_id": str(previous_session.id),
            "rows": [
                {"full_name": "Amina Yusuf", "class_arm_id": str(previous_arms[0].id)}
            ],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 1
    assert r.json()["session"]["name"] == "2025/2026"

    enrollment = db.scalar(
        select(StudentEnrollment).where(StudentEnrollment.school_id == school_uuid)
    )
    assert enrollment is not None
    assert enrollment.academic_session_id == previous_session.id


def test_bulk_add_rejects_a_class_from_another_school(client, db):
    from app.services.tenancy_service import create_school

    register_school(client)
    sid = active_school_id(client)
    _session_a, _arms_a = _add_session_arms(db, uuid.UUID(sid))

    other = create_school(db, name="Other Academy", school_type="secondary")
    db.flush()
    _session_b, arms_b = _add_session_arms(db, other.id)

    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/students/bulk",
        json={"rows": [{"full_name": "Ada Obi", "class_arm_id": str(arms_b[0].id)}]},
    )
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["created"] == 0 and result["failed"] == 1
    assert "not found" in result["errors"][0]["message"].lower()

    assert db.scalar(select(Student).where(Student.school_id == uuid.UUID(sid))) is None


def test_bulk_add_students_requires_a_session(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/students/bulk",
        json={"rows": [{"full_name": "Ada Obi", "class_arm_id": str(uuid.uuid4())}]},
    )
    assert r.status_code == 422, r.text
    assert "no current academic session" in r.json()["error"]["message"].lower()


def test_bulk_add_keeps_the_good_rows_when_one_fails(client, db):
    register_school(client)
    sid = active_school_id(client)
    school_uuid = uuid.UUID(sid)
    _session, arms = _add_session_arms(db, school_uuid)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/students/bulk",
        json={
            "rows": [
                {"full_name": "Ada Obi", "class_arm_id": str(arms[0].id)},
                {"full_name": "Cher", "class_arm_id": str(arms[0].id)},
                {"full_name": "Tunde Bakare", "class_arm_id": str(arms[1].id)},
            ]
        },
    )
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["created"] == 2 and result["failed"] == 1
    assert result["errors"][0]["index"] == 1
    assert result["errors"][0]["full_name"] == "Cher"

    students = db.scalars(select(Student).where(Student.school_id == school_uuid)).all()
    assert {s.first_name for s in students} == {"Ada", "Tunde"}
    assert len({s.admission_no for s in students}) == 2


def test_create_class_in_an_existing_session(client, db):
    register_school(client)
    sid = active_school_id(client)
    school_uuid = uuid.UUID(sid)
    session, _arms = _add_session_arms(db, school_uuid, arms=("JSS 1A",))
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/classes",
        json={"name": "  JSS 1B  ", "session_id": str(session.id)},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] is True
    assert body["class_arm"]["name"] == "JSS 1B"
    assert body["class_arm"]["students"] == 0
    assert body["session"]["id"] == str(session.id)

    r = client.get(f"{SUPER}/schools/{sid}/classes")
    names = {a["name"] for a in r.json()["sessions"][0]["arms"]}
    assert names == {"JSS 1A", "JSS 1B"}


def test_create_class_creates_the_first_session(client, db):
    register_school(client)
    sid = active_school_id(client)
    school_uuid = uuid.UUID(sid)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/classes",
        json={"name": "Primary 1", "session_name": "2025/2026"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] is True
    assert body["session"]["name"] == "2025/2026"
    assert body["session"]["is_current"] is True

    sessions = db.scalars(
        select(AcademicSession).where(AcademicSession.school_id == school_uuid)
    ).all()
    assert len(sessions) == 1 and sessions[0].is_current is True
    assert sessions[0].id == uuid.UUID(body["session"]["id"])


def test_create_class_is_idempotent_by_name(client, db):
    register_school(client)
    sid = active_school_id(client)
    session, _arms = _add_session_arms(db, uuid.UUID(sid))
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    first = client.post(
        f"{SUPER}/schools/{sid}/classes",
        json={"name": "JSS 1C", "session_id": str(session.id)},
    )
    assert first.status_code == 201, first.text
    assert first.json()["created"] is True

    second = client.post(
        f"{SUPER}/schools/{sid}/classes",
        json={"name": "jss 1c", "session_id": str(session.id)},
    )
    assert second.status_code == 201, second.text
    assert second.json()["created"] is False
    assert second.json()["class_arm"]["id"] == first.json()["class_arm"]["id"]


def test_create_class_rejects_another_schools_session(client, db):
    from app.services.tenancy_service import create_school

    register_school(client)
    sid = active_school_id(client)
    _add_session_arms(db, uuid.UUID(sid))

    other = create_school(db, name="Other Academy", school_type="secondary")
    db.flush()
    other_session, _other_arms = _add_session_arms(db, other.id)

    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(
        f"{SUPER}/schools/{sid}/classes",
        json={"name": "JSS 1A", "session_id": str(other_session.id)},
    )
    assert r.status_code == 422, r.text
    assert "not found" in r.json()["error"]["message"].lower()


def test_create_class_without_a_session_needs_a_name(client, db):
    register_school(client)
    sid = active_school_id(client)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    r = client.post(f"{SUPER}/schools/{sid}/classes", json={"name": "JSS 1A"})
    assert r.status_code == 422, r.text
    assert "no academic session" in r.json()["error"]["message"].lower()


def test_create_class_then_bulk_add_uses_it(client, db):
    register_school(client)
    sid = active_school_id(client)
    school_uuid = uuid.UUID(sid)
    admin = _create_platform_admin(db)
    _login(client, admin.email)

    created = client.post(
        f"{SUPER}/schools/{sid}/classes",
        json={"name": "Nursery 2", "session_name": "2026/2027"},
    )
    assert created.status_code == 201, created.text
    arm_id = created.json()["class_arm"]["id"]
    session_id = created.json()["session"]["id"]

    r = client.post(
        f"{SUPER}/schools/{sid}/students/bulk",
        json={
            "session_id": session_id,
            "rows": [{"full_name": "Ada Obi", "class_arm_id": arm_id}],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 1
    assert r.json()["students"][0]["class_arm_name"] == "Nursery 2"

    enrollment = db.scalar(
        select(StudentEnrollment).where(StudentEnrollment.school_id == school_uuid)
    )
    assert enrollment is not None and str(enrollment.class_arm_id) == arm_id
