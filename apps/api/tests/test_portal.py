"""Result-portal tests: result-code issuance (exam office) and the public checks.

The portal is deliberately narrow. These tests pin the defensive behavior:

* Issuing the result code requires ``results.report_card`` (the exam office's
  capability), whether it is the school-wide code or a per-student code.
* Any check failure — wrong code, unknown admission no, unknown or revoked
  credential — answers the *same* generic 404 so the endpoint can't enumerate
  schools, students or live codes.
* The portal token only unlocks published subjects, and bad/expired/wrong-scope
  tokens are rejected at the report endpoint.
* The codes carry the school's initials and rotation revokes the old one.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.models import Role, SchoolMembership, SchoolResultPin, User
from app.services.portal_service import school_initials
from app.seed import seed_grade_scale
from .conftest import active_school_id, grant_permission, register_school

PUBLIC = "/api/public"
CODE = "/api/results/portal-pin"


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

    # These tests exercise the scoring engine as a user who may enter marks.
    # The admin templates omit results.enter by policy (see test_result_access),
    # so the founding admin opts back in for this transaction.
    grant_permission(db, school_id, "results.enter")

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
    # Hand-craft a valid portal token to isolate the 404 source (no credential
    # check is involved).
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


# --- School initials -------------------------------------------------------------
def test_initials_read_naturally_from_the_school_name():
    """The prefix is the part a parent recognises, so it has to be derivable and
    stable — including when the name carries a noise word."""

    class _S:
        def __init__(self, name, short_name=None):
            self.name = name
            self.short_name = short_name

    assert school_initials(_S("Green Valley Grammar School")) == "GVGS"
    assert school_initials(_S("Test Academy")) == "TA"
    assert school_initials(_S("University of Lagos")) == "UL"
    assert school_initials(_S("Clearis")) == "CLE"  # single word → first letters
    assert school_initials(_S("St. Mary's College")) == "SMC"  # "'s" is not an initial
    assert school_initials(_S("...")) == "SCH"  # nothing usable → safe fallback
    # A short name wins, and a single-token one is already an abbreviation.
    assert school_initials(_S("Green Valley Grammar School", "GVGS")) == "GVGS"
    assert school_initials(_S("Green Valley Grammar School", "Green Valley")) == "GV"


# --- School result code: issuance -------------------------------------------------
def test_issue_code_requires_results_report_card(client, db):
    """The code is the Exam Office's document, so ``students.edit`` is not enough."""
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    # Unauthenticated: rejected at the door.
    assert client.get(CODE).status_code == 401

    # A teacher may enter and submit results but not process report cards.
    user = _add_limited_user(db, sid, "teacher")
    client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Str0ng!Pass"},
    )
    r = client.post(f"{CODE}", headers={"X-School-Id": sid})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_code_is_null_until_issued_then_carries_school_initials(client):
    register_school(client, name="Green Valley Grammar School")
    sid = active_school_id(client)

    r = client.get(CODE, headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json() is None  # never issued, and that must read as null

    r = client.post(CODE, headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["prefix"] == "GVGS"
    assert body["active"] is True
    assert body["use_count"] == 0
    assert body["last_used_at"] is None
    # The initials are prepended and the random block is unambiguous by design
    # (no 0/O/1/I/L, which a parent reading a printout cannot tell apart).
    assert re.fullmatch(r"GVGS-[A-Z2-9]{5}", body["code"]), body["code"]
    assert not set(body["code"].split("-")[1]) & set("OIL01")

    # Reading it back returns the same live code.
    assert client.get(CODE, headers={"X-School-Id": sid}).json()["code"] == body["code"]


def test_rotation_revokes_the_previous_code(client, db):
    register_school(client)
    sid = active_school_id(client)
    first = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]
    second = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]
    assert first != second

    rows = db.scalars(
        select(SchoolResultPin).order_by(SchoolResultPin.created_at)
    ).all()
    assert len(rows) == 2
    assert rows[0].revoked_at is not None  # kept for audit
    assert rows[1].revoked_at is None
    assert client.get(CODE, headers={"X-School-Id": sid}).json()["code"] == second


def test_withdraw_code_removes_parent_access(client):
    register_school(client)
    sid = active_school_id(client)
    code = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]

    r = client.delete(CODE, headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["active"] is False
    assert client.get(CODE, headers={"X-School-Id": sid}).json() is None

    # A withdrawn code is dead at the public door too.
    register_school(client, name="Orbit Academy", email="orbit@test.edu")
    r = client.post(f"{PUBLIC}/result-check", json={"pin": code, "admission_no": "STU-001"})
    assert r.status_code == 404


def test_withdraw_without_a_live_code_is_404(client):
    register_school(client)
    sid = active_school_id(client)
    r = client.delete(CODE, headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- School result code: the public check-in ----------------------------------------
def test_result_check_unlocks_published_card(client, db):
    register_school(client, name="Green Valley Grammar School")
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    code = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]

    r = client.post(
        f"{PUBLIC}/result-check",
        json={"pin": code, "admission_no": "STU-001"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["student"]["full_name"] == "Aisha Bello"
    # The code names the school, so the response must say which one it was.
    assert body["school"]["name"] == "Green Valley Grammar School"
    assert body["expires_minutes"] == 30
    token = body["token"]

    # The term picker is scoped by the token itself.
    r = client.get(f"{PUBLIC}/terms", params={"token": token})
    assert r.status_code == 200, r.text
    terms = r.json()
    assert [t["id"] for t in terms] == [w["term_id"]]
    assert terms[0]["session_name"] == "2025/2026"

    r = client.get(
        f"{PUBLIC}/report-card",
        params={"token": token, "term_id": w["term_id"]},
    )
    assert r.status_code == 200, r.text
    card = r.json()
    assert [s["subject_name"] for s in card["subjects"]] == ["Mathematics"]
    assert card["summary"]["total"] == 60.0

    # A successful check is stamped on the code for the office to see.
    row = db.scalar(
        select(SchoolResultPin).where(SchoolResultPin.revoked_at.is_(None))
    )
    assert row.use_count == 1
    assert row.last_used_at is not None


def test_result_check_accepts_the_code_without_its_dash(client, db):
    """Parents retype the code by hand; ``GVS7K42Q`` must work like ``GVS-7K42Q``."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    code = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]

    for variant in (code.replace("-", ""), code.lower(), f"  {code}  "):
        r = client.post(
            f"{PUBLIC}/result-check",
            json={"pin": variant, "admission_no": "STU-001"},
        )
        assert r.status_code == 200, (variant, r.text)


def test_result_check_generic_404_on_every_failure(client, db):
    """Wrong code, unknown admission, unknown student in the right school, and a
    rotated-away code — all one generic 404 with one message."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    code = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]
    old = code
    new = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]
    assert old != new

    cases = [
        {"pin": "ZZZZ-22222", "admission_no": "STU-001"},  # no such code
        {"pin": new, "admission_no": "STU-999"},  # no such student
        {"pin": "", "admission_no": "STU-001"},  # blank (422 below)
        {"pin": old, "admission_no": "STU-001"},  # rotated away
    ]
    for body in cases:
        r = client.post(f"{PUBLIC}/result-check", json=body)
        if not body["pin"]:
            assert r.status_code == 422, body
            continue
        assert r.status_code == 404, body
        err = r.json()["error"]
        assert err["code"] == "ERR_NOT_FOUND"
        # Never hints which half of the credential was wrong.
        assert err["message"] == "Invalid portal credentials"


def test_result_check_case_insensitive_code_does_not_leak_schools(client, db):
    """A code from a *different* school must not unlock this school's student,
    even with a correct admission number (the code names the tenant)."""
    register_school(client, name="First Academy", email="first@test.edu")
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)

    register_school(client, name="Other Academy", email="other@test.edu")
    other_code = client.post(
        CODE, headers={"X-School-Id": active_school_id(client)}
    ).json()["code"]

    # Correct admission number, wrong school's code → nothing is revealed.
    r = client.post(
        f"{PUBLIC}/result-check",
        json={"pin": other_code, "admission_no": "STU-001"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["message"] == "Invalid portal credentials"


def test_terms_requires_a_valid_portal_token(client):
    register_school(client)
    assert client.get(f"{PUBLIC}/terms", params={"token": "nope"}).status_code == 404
    assert (
        client.get(f"{PUBLIC}/terms", params={"token": _token_with_exp(str(uuid.uuid4()), str(uuid.uuid4()))}).status_code
        == 200
    )


# --- Per-student result codes (the login screen's credential) ------------------------
CODES = "/api/results/portal-codes"


def test_issue_student_code_requires_results_report_card(client, db):
    """Issuing a student's code is the Exam Office's job, like the report card."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)

    assert client.get(CODES).status_code == 401

    user = _add_limited_user(db, sid, "teacher")
    client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Str0ng!Pass"},
    )
    r = client.post(f"{CODES}/{w['student_ids'][0]}", headers={"X-School-Id": sid})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_student_code_carries_initials_and_lists_students(client, db):
    register_school(client, name="Green Valley Grammar School")
    sid = active_school_id(client)
    w = _configure(client, sid, db)

    # Every student is listed, but no code is issued until asked for.
    rows = client.get(CODES, headers={"X-School-Id": sid}).json()
    assert len(rows) == 3
    assert all(r["code"] is None and r["active"] is False for r in rows)

    r = client.post(f"{CODES}/{w['student_ids'][0]}", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active"] is True
    assert body["prefix"] == "GVGS"
    assert body["student_name"] == "Aisha Bello"
    # Same unambiguous alphabet as the school code: no 0/O, 1/I/L, 5/S.
    assert re.fullmatch(r"GVGS-[A-Z2-9]{5}", body["code"]), body["code"]
    assert not set(body["code"].split("-")[1]) & set("OIL01")

    rows = client.get(CODES, headers={"X-School-Id": sid}).json()
    aisha = next(r for r in rows if r["student_id"] == w["student_ids"][0])
    assert aisha["code"] == body["code"]


def test_code_alone_unlocks_the_student(client, db):
    """The point of the change: no admission number on the public check-in."""
    register_school(client, name="Green Valley Grammar School")
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    code = client.post(
        f"{CODES}/{w['student_ids'][0]}", headers={"X-School-Id": sid}
    ).json()["code"]

    # Only the code — no admission_no in the payload at all.
    r = client.post(f"{PUBLIC}/result-check", json={"pin": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["student"]["full_name"] == "Aisha Bello"
    assert body["school"]["name"] == "Green Valley Grammar School"

    card = client.get(
        f"{PUBLIC}/report-card",
        params={"token": body["token"], "term_id": w["term_id"]},
    )
    assert card.status_code == 200, card.text
    assert card.json()["summary"]["total"] == 60.0

    # The dash-less and lower-case forms work, just like the school code.
    assert client.post(
        f"{PUBLIC}/result-check", json={"pin": code.replace("-", "")}
    ).status_code == 200
    assert client.post(
        f"{PUBLIC}/result-check", json={"pin": code.lower()}
    ).status_code == 200

    # A successful check is stamped for the office to see.
    from app.models import StudentResultCode

    row = db.scalar(
        select(StudentResultCode).where(StudentResultCode.revoked_at.is_(None))
    )
    assert row.use_count >= 3
    assert row.last_used_at is not None


def test_rotating_a_student_code_revokes_the_old_one(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]

    first = client.post(f"{CODES}/{student_id}", headers={"X-School-Id": sid}).json()["code"]
    second = client.post(f"{CODES}/{student_id}", headers={"X-School-Id": sid}).json()["code"]
    assert first != second

    assert client.post(f"{PUBLIC}/result-check", json={"pin": first}).status_code == 404
    assert client.post(f"{PUBLIC}/result-check", json={"pin": second}).status_code == 200


def test_withdraw_student_code_kills_access(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]
    code = client.post(f"{CODES}/{student_id}", headers={"X-School-Id": sid}).json()["code"]

    r = client.delete(f"{CODES}/{student_id}", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["active"] is False
    assert client.post(f"{PUBLIC}/result-check", json={"pin": code}).status_code == 404

    # Nothing live to withdraw a second time.
    r = client.delete(f"{CODES}/{student_id}", headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_generate_missing_codes_fills_only_the_gaps(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    existing = client.post(
        f"{CODES}/{w['student_ids'][0]}", headers={"X-School-Id": sid}
    ).json()["code"]

    r = client.post(f"{CODES}/generate", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["issued"] == 2  # the other two students, not all three
    assert body["total"] == 3

    rows = client.get(CODES, headers={"X-School-Id": sid}).json()
    assert all(r["active"] for r in rows)
    # The first student's code was left untouched.
    first = next(r for r in rows if r["student_id"] == w["student_ids"][0])
    assert first["code"] == existing

    # Running it again issues nothing.
    assert client.post(f"{CODES}/generate", headers={"X-School-Id": sid}).json()["issued"] == 0


def test_student_code_unknown_is_a_generic_404(client):
    register_school(client)
    r = client.post(f"{PUBLIC}/result-check", json={"pin": "ZZZZ-22222"})
    assert r.status_code == 404
    assert r.json()["error"]["message"] == "Invalid portal credentials"


def test_student_code_resolves_to_its_own_school(client, db):
    """A student code names the tenant too — it must never open another school."""
    register_school(client, name="First Academy", email="first@test.edu")
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    code = client.post(
        f"{CODES}/{w['student_ids'][0]}", headers={"X-School-Id": sid}
    ).json()["code"]

    r = client.post(f"{PUBLIC}/result-check", json={"pin": code})
    assert r.status_code == 200, r.text
    assert r.json()["school"]["name"] == "First Academy"

    # The legacy school-wide code still works, but only with an admission no.
    school_code = client.post(CODE, headers={"X-School-Id": sid}).json()["code"]
    assert client.post(f"{PUBLIC}/result-check", json={"pin": school_code}).status_code == 404
    assert (
        client.post(
            f"{PUBLIC}/result-check",
            json={"pin": school_code, "admission_no": "STU-001"},
        ).status_code
        == 200
    )