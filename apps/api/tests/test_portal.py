"""Result-portal tests: PIN issuance (admin) + the public PIN-check flow.

The portal is deliberately narrow. These tests pin the defensive behavior:

* ``PUT /students/{id}/pin`` requires ``students.edit``.
* Any PIN-check failure — wrong PIN, unknown admission no, unknown school —
  answers the *same* generic 404 so the endpoint can't enumerate students.
* The portal token only unlocks published subjects, and bad/expired/wrong-scope
  tokens are rejected at the report endpoint.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.models import Role, SchoolMembership, StudentPin, User
from app.seed import seed_grade_scale
from .conftest import active_school_id, register_school

PUBLIC = "/api/public"
PIN = "/api/students"


# --- World builders (mirror test_results.py, kept local for isolation) ----------
def _configure(client, school_id: str, db: Session) -> dict:
    """Create session, term, arm, subject, offering, three students."""
    r = client.post(
        "/api/academics/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": school_id},
    )
    session_id = r.json()["id"]
    r = client.post(
        "/api/academics/terms",
        json={"session_id": session_id, "term_no": 1, "name": "First Term"},
        headers={"X-School-Id": school_id},
    )
    term_id = r.json()["id"]
    # The admin must activate the session + term before any results work.
    r = client.post(
        f"/api/academics/sessions/{session_id}/activate",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/academics/terms/{term_id}/activate",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/academics/arms",
        json={"session_id": session_id, "name": "JSS 1 A"},
        headers={"X-School-Id": school_id},
    )
    arm_id = r.json()["id"]
    r = client.post(
        "/api/academics/subjects",
        json={"name": "Mathematics", "code": "MTH"},
        headers={"X-School-Id": school_id},
    )
    subject_id = r.json()["id"]
    r = client.post(
        "/api/academics/offerings",
        json={"arm_id": arm_id, "subject_id": subject_id},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text

    # The WAEC 9-point scale drives grade mapping in the report card.
    seed_grade_scale(db, school_id)

    enrollment_ids, student_ids = [], []
    for i, (first, last) in enumerate(
        [("Aisha", "Bello"), ("David", "Okafor"), ("Tolu", "Coker")], start=1
    ):
        r = client.post(
            "/api/students",
            json={
                "admission_no": f"STU-{i:03d}",
                "first_name": first,
                "last_name": last,
                "gender": "female" if i % 2 == 0 else "male",
            },
            headers={"X-School-Id": school_id},
        )
        assert r.status_code == 201, r.text
        student_ids.append(r.json()["id"])
        r = client.post(
            "/api/students/enrollments",
            json={
                "student_id": student_ids[-1],
                "arm_id": arm_id,
                "session_id": session_id,
            },
            headers={"X-School-Id": school_id},
        )
        assert r.status_code == 201, r.text
        enrollment_ids.append(r.json()["id"])

    return {
        "session_id": session_id,
        "term_id": term_id,
        "arm_id": arm_id,
        "subject_id": subject_id,
        "enrollment_ids": enrollment_ids,
        "student_ids": student_ids,
    }


def _add_components(client, school_id: str, term_id: str) -> dict:
    ids = {}
    for name, weight in [("CA1", 20), ("CA2", 30), ("Exam", 50)]:
        r = client.post(
            "/api/results/components",
            json={"term_id": term_id, "name": name, "max_score": 100, "weight": weight},
            headers={"X-School-Id": school_id},
        )
        assert r.status_code == 201, r.text
        ids[name] = r.json()["id"]
    return ids


def _enter_all(client, sid, w, comps, score=60):
    entries = [
        {
            "student_enrollment_id": env_id,
            "scores": [
                {"assessment_component_id": comps[comp], "score": score}
                for comp in ("CA1", "CA2", "Exam")
            ],
        }
        for env_id in w["enrollment_ids"]
    ]
    r = client.put(
        "/api/results/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": entries,
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text


def _act(client, sid, w, action):
    return client.post(
        f"/api/results/{action}",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
        },
        headers={"X-School-Id": sid},
    )


def _publish(client, sid, w, comps):
    _enter_all(client, sid, w, comps)
    for step in ("submit", "verify", "approve", "publish"):
        assert _act(client, sid, w, step).status_code == 200, step


def _school_slug(client) -> str:
    return client.get("/api/auth/me").json()["memberships"][0]["school_slug"]


def _add_limited_user(db: Session, school_id: str, role_code: str) -> User:
    """Create a user whose membership carries only the given template role."""
    role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == role_code)
    )
    assert role is not None, f"{role_code} template role missing"
    user = User(
        email=f"{role_code}-{uuid.uuid4().hex[:8]}@school.example",
        password_hash=hash_password("Str0ng!Pass"),
        full_name=role_code.replace("_", " ").title(),
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return user


# --- PIN issuance ---------------------------------------------------------------
def test_set_pin_requires_students_edit(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)

    # Unauthenticated: rejected at the door.
    r = client.put(f"{PIN}/{w['student_ids'][0]}/pin", json={"pin": "1234"})
    assert r.status_code == 401

    # The secretary template has students.view but NOT students.edit.
    user = _add_limited_user(db, sid, "secretary")
    client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Str0ng!Pass"},
    )
    r = client.put(
        f"{PIN}/{w['student_ids'][0]}/pin",
        json={"pin": "1234"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_set_and_rotate_pin(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]

    r = client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "4321"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["student_id"] == student_id

    rows = db.scalars(
        select(StudentPin).where(StudentPin.student_id == student_id)
    ).all()
    assert len(rows) == 1
    assert rows[0].revoked_at is None
    assert rows[0].pin_hash != "4321"  # hashed, never plaintext

    # Rotation replaces the live row; the old one stays revoked for audit.
    r = client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "9999"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    rows = db.scalars(
        select(StudentPin)
        .where(StudentPin.student_id == student_id)
        .order_by(StudentPin.created_at)
    ).all()
    assert len(rows) == 2
    assert rows[0].revoked_at is not None
    assert rows[1].revoked_at is None


def test_pin_must_be_digits(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)

    r = client.put(
        f"{PIN}/{w['student_ids'][0]}/pin",
        json={"pin": "12ab56"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


# --- Public PIN check -----------------------------------------------------------
def test_pin_check_happy_path_unlocks_published_card(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    student_id = w["student_ids"][0]

    r = client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "2468"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"{PUBLIC}/pin-check",
        json={
            "school_slug": _school_slug(client),
            "admission_no": "STU-001",
            "pin": "2468",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["student"]["full_name"] == "Aisha Bello"
    assert body["student"]["admission_no"] == "STU-001"
    assert body["expires_minutes"] == 30
    token = body["token"]

    # The token unlocks only published subjects.
    r = client.get(
        f"{PUBLIC}/report-card",
        params={"token": token, "term_id": w["term_id"]},
    )
    assert r.status_code == 200, r.text
    card = r.json()
    assert [s["subject_name"] for s in card["subjects"]] == ["Mathematics"]
    assert card["summary"]["total"] == 60.0
    assert card["summary"]["class_rank"] == 1


def test_pin_check_generic_404_on_every_failure(client, db):
    """Wrong PIN, unknown admission, unknown school — all one generic 404."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]
    client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "2468"},
        headers={"X-School-Id": sid},
    )
    slug = _school_slug(client)

    cases = [
        {"school_slug": slug, "admission_no": "STU-001", "pin": "0000"},  # bad pin
        {"school_slug": slug, "admission_no": "STU-999", "pin": "2468"},  # unknown student
        {"school_slug": "no-such-school", "admission_no": "STU-001", "pin": "2468"},
    ]
    for body in cases:
        r = client.post(f"{PUBLIC}/pin-check", json=body)
        assert r.status_code == 404, body
        err = r.json()["error"]
        assert err["code"] == "ERR_NOT_FOUND"
        assert err["message"] == "Invalid portal credentials"


def test_pin_check_stamps_last_used(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]
    client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "2468"},
        headers={"X-School-Id": sid},
    )
    client.post(
        f"{PUBLIC}/pin-check",
        json={
            "school_slug": _school_slug(client),
            "admission_no": "STU-001",
            "pin": "2468",
        },
    )
    row = db.scalar(
        select(StudentPin).where(
            StudentPin.student_id == student_id, StudentPin.revoked_at.is_(None)
        )
    )
    assert row.last_used_at is not None


def test_pin_check_rejects_revoked_pin(client, db):
    """A rotated-away PIN must not unlock anything."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]
    r = client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "2468"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "9999"},
        headers={"X-School-Id": sid},
    )

    r = client.post(
        f"{PUBLIC}/pin-check",
        json={
            "school_slug": _school_slug(client),
            "admission_no": "STU-001",
            "pin": "2468",
        },
    )
    assert r.status_code == 404
    assert r.json()["error"]["message"] == "Invalid portal credentials"


# --- Portal tokens --------------------------------------------------------------
def _token_with(claims: dict) -> str:
    return jwt.encode(
        claims, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def test_report_card_rejects_bad_tokens(client):
    register_school(client)
    r = client.get(
        f"{PUBLIC}/report-card",
        params={"token": "not-a-jwt", "term_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    # A normal (user) access token carries no portal scope.
    from app.core.security import create_access_token

    r = client.get(
        f"{PUBLIC}/report-card",
        params={"token": create_access_token(str(uuid.uuid4())), "term_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


def test_report_card_rejects_expired_token(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    expired = _token_with_past_exp(sid, w["student_ids"][0])

    r = client.get(
        f"{PUBLIC}/report-card",
        params={"token": expired, "term_id": w["term_id"]},
    )
    assert r.status_code == 404


def _token_with_past_exp(school_id: str, student_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": student_id,
            "school": school_id,
            "scope": "portal",
            "iat": now - timedelta(minutes=60),
            "exp": now - timedelta(minutes=30),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def test_public_schools_lists_school(client):
    register_school(client, name="Public Academy", email="pub@test.edu")
    r = client.get(f"{PUBLIC}/schools")
    assert r.status_code == 200
    body = r.json()
    assert any(s["slug"] == _school_slug(client) for s in body)


def test_public_report_card_404_when_nothing_published(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]
    client.put(
        f"{PIN}/{student_id}/pin", json={"pin": "2468"},
        headers={"X-School-Id": sid},
    )
    # No PIN check; hand-craft a valid portal token to isolate the 404 source.
    token = _token_with_exp(sid, student_id, minutes=30)
    r = client.get(
        f"{PUBLIC}/report-card",
        params={"token": token, "term_id": w["term_id"]},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def _token_with_exp(school_id: str, student_id: str, minutes: int = 30) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": student_id,
            "school": school_id,
            "scope": "portal",
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )