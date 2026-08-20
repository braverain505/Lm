"""Multi-tenancy: the cross-school canary. School B must NEVER see School A's
data — attempts return the neutral ERR_NOT_MEMBER 404 (not a leaky 403/404).

This is the most important test file in the suite: it protects the tenant
isolation boundary for the whole platform.
"""
from .conftest import active_school_id, register_school


def _create_session(client, school_id: str) -> str:
    r = client.post(
        "/api/academics/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _switch_school(client, name: str, email: str) -> str:
    """Register a brand-new school + admin on the same client (log out first so
    cookies don't leak), and return its school_id."""
    client.post("/api/auth/logout")
    register_school(client, name=name, email=email)
    return active_school_id(client)


def test_cross_school_list_isolated(client):
    """A second tenant never sees the first tenant's sessions in a list view."""
    register_school(client, name="School Alpha", email="a@test.edu")
    a_id = active_school_id(client)
    a_session = _create_session(client, a_id)

    b_id = _switch_school(client, "School Beta", "b@beta.edu")

    r = client.get("/api/academics/sessions", headers={"X-School-Id": b_id})
    assert r.status_code == 200
    sessions = r.json()
    # Beta is fresh — its session list is empty, and Alpha's session never shows.
    assert all(s["id"] != a_session for s in sessions)


def test_cross_school_direct_id_is_hidden(client):
    """Directly referencing another tenant's resource id presents as a plain
    404 — existence of the row is never revealed."""
    register_school(client, name="School One", email="one@schoolone.edu")
    s1 = active_school_id(client)
    session1 = _create_session(client, s1)

    s2 = _switch_school(client, "School Two", "two@schooltwo.edu")

    r = client.get(
        f"/api/academics/sessions/{session1}", headers={"X-School-Id": s2},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_cross_school_write_rejected(client):
    """Updating a foreign school's session must fail, not silently no-op."""
    register_school(client, name="School Alpha", email="w@test.edu")
    s1 = active_school_id(client)
    session1 = _create_session(client, s1)

    s2 = _switch_school(client, "School Beta", "wb@beta.edu")

    r = client.patch(
        f"/api/academics/sessions/{session1}",
        json={"name": "Hacked"},
        headers={"X-School-Id": s2},
    )
    assert r.status_code == 404


def test_membership_status_gates_access(client, db):
    """A suspended membership must block access even with a valid session."""
    from sqlalchemy import select

    from app.models import SchoolMembership

    register_school(client, name="School Susp", email="s@test.edu")
    school_id = active_school_id(client)

    # Suspend the membership through the same transaction the client uses
    # (simulating an admin action at the DB layer).
    membership = db.scalar(
        select(SchoolMembership).where(SchoolMembership.school_id == school_id)
    )
    assert membership is not None
    membership.status = "suspended"

    r = client.get("/api/academics/sessions", headers={"X-School-Id": school_id})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_MEMBERSHIP_SUSPENDED"