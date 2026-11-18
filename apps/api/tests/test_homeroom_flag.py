"""Who counts as a homeroom teacher: the assignment, not the role label.

The psychomotor record is the class teacher's. The API has always decided that by
asking whether the caller's staff record is the arm's ``class_teacher`` — but the
navigation and the psychomotor screen asked the *role code* instead. Schools set a
form teacher on the class and usually leave them on the ordinary ``teacher`` role,
so most real homeroom teachers never saw the feature (El Gibbor: one form teacher,
none carrying the label; La'ashinre: 13 form teachers, 3 carrying it).

These tests pin the flag the navigation now reads.
"""
import uuid

from app.models import ClassArm, Staff

from .conftest import active_school_id, register_school
from .test_staff_accounts import _add_staff, _create_account
from .test_student_scope import _world

ME = "/api/auth/me"


def _login(client, email: str, password: str = "Str0ng!Pass") -> None:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def _membership(client) -> dict:
    r = client.get(ME)
    assert r.status_code == 200, r.text
    return r.json()["memberships"][0]


def test_a_class_teacher_on_the_plain_teacher_role_is_flagged_as_homeroom(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)

    staff = _add_staff(client, sid, staff_no="T200")
    r = _create_account(client, sid, staff["id"], email="form@test.edu", role_code="teacher")
    assert r.status_code == 201, r.text

    # The school sets them as the form teacher of JSS 1 A. No role change.
    arm = db.get(ClassArm, uuid.UUID(w["arms"]["JSS 1 A"]))
    arm.class_teacher_id = uuid.UUID(staff["id"])
    db.flush()

    _login(client, "form@test.edu")
    membership = _membership(client)
    assert membership["role"]["code"] == "teacher"
    assert membership["is_homeroom_teacher"] is True


def test_a_teacher_who_teaches_but_is_nobodys_class_teacher_is_not_flagged(client, db):
    register_school(client)
    sid = active_school_id(client)
    _world(client, sid)

    staff = _add_staff(client, sid, staff_no="T201")
    r = _create_account(client, sid, staff["id"], email="subject@test.edu", role_code="teacher")
    assert r.status_code == 201, r.text

    _login(client, "subject@test.edu")
    assert _membership(client)["is_homeroom_teacher"] is False


def test_the_role_label_alone_does_not_make_someone_a_homeroom_teacher(client, db):
    register_school(client)
    sid = active_school_id(client)
    _world(client, sid)

    staff = _add_staff(client, sid, staff_no="T202")
    r = _create_account(
        client, sid, staff["id"], email="labelled@test.edu", role_code="homeroom_teacher"
    )
    assert r.status_code == 201, r.text

    _login(client, "labelled@test.edu")
    membership = _membership(client)
    assert membership["role"]["code"] == "homeroom_teacher"
    assert membership["is_homeroom_teacher"] is False


def test_the_school_owner_is_not_flagged(client, db):
    register_school(client)
    _world(client, active_school_id(client))
    assert _membership(client)["is_homeroom_teacher"] is False