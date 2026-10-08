"""Staff account provisioning: an admin (users.manage) creates a login
account (email + password + role) for a staff member, and that member can then
sign in with their own credentials and receives only their role's permissions."""
import uuid

from .conftest import active_school_id, register_school
from .test_portal import _add_limited_user

STAFF = "/api/staff"


def _add_staff(client, school_id: str, *, staff_no: str, full_name: str = "Grace Teacher") -> dict:
    r = client.post(
        STAFF,
        json={"staff_no": staff_no, "full_name": full_name, "membership_type": "teaching"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _role_id(client, school_id: str, code: str) -> str:
    r = client.get("/api/roles", headers={"X-School-Id": school_id})
    assert r.status_code == 200, r.text
    role = next(x for x in r.json() if x["code"] == code)
    return role["id"]


def _create_account(
    client, school_id: str, staff_id: str, *, email: str, password: str = "Str0ng!Pass", role_code: str = "teacher"
):
    return client.post(
        f"{STAFF}/{staff_id}/account",
        json={"email": email, "password": password, "role_id": _role_id(client, school_id, role_code)},
        headers={"X-School-Id": school_id},
    )


def test_admin_creates_staff_account_and_teacher_logs_in(client):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T001")

    r = _create_account(client, sid, staff["id"], email="grace@test.edu")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["staff_id"] == staff["id"]
    assert body["email"] == "grace@test.edu"
    assert body["role_code"] == "teacher"

    # The staff member can now sign in with their own credentials.
    login = client.post(
        "/api/auth/login", json={"email": "grace@test.edu", "password": "Str0ng!Pass"}
    )
    assert login.status_code == 200, login.text
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    memberships = me.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["school_id"] == sid
    assert memberships[0]["role"]["code"] == "teacher"
    # A teacher has no user-management powers.
    assert "users.manage" not in memberships[0]["permissions"]


def test_account_provisioning_requires_users_manage(client, db):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T002")

    # Secretary has staff.view but not users.manage.
    user = _add_limited_user(db, sid, "secretary")
    client.post("/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"})
    r = _create_account(client, sid, staff["id"], email="no@test.edu")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_duplicate_email_and_password_rules(client):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T003")
    r = _create_account(client, sid, staff["id"], email="dup@test.edu")
    assert r.status_code == 201

    # Same email for a different staff member → conflict.
    staff2 = _add_staff(client, sid, staff_no="T004")
    r = _create_account(client, sid, staff2["id"], email="dup@test.edu")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"

    # Short password → 422 validation.
    staff3 = _add_staff(client, sid, staff_no="T005")
    r = _create_account(client, sid, staff3["id"], email="weak@test.edu", password="short")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"

    # Re-provisioning the same staff member → conflict.
    r = _create_account(client, sid, staff["id"], email="again@test.edu")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"


def test_role_must_belong_to_school(client):
    register_school(client, name="First Academy", email="first@test.edu")
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T006")
    register_school(client, name="Second Academy", email="second@test.edu")
    sid2 = active_school_id(client)
    other_role = _role_id(client, sid2, "teacher")
    # Log back in as the first school's admin.
    client.post("/api/auth/login", json={"email": "first@test.edu", "password": "Str0ng!Pass"})

    r = client.post(
        f"{STAFF}/{staff['id']}/account",
        json={"email": "cross@test.edu", "password": "Str0ng!Pass", "role_id": other_role},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_staff_account_404_for_foreign_staff(client):
    register_school(client, name="Alpha", email="alpha@test.edu")
    sid = active_school_id(client)
    register_school(client, name="Beta", email="beta@test.edu")
    sid2 = active_school_id(client)
    staff_beta = _add_staff(client, sid2, staff_no="T007")
    client.post("/api/auth/login", json={"email": "alpha@test.edu", "password": "Str0ng!Pass"})

    r = _create_account(client, sid, staff_beta["id"], email="foreign@test.edu")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_homeroom_role_requires_and_sets_a_class(client):
    """A homeroom teacher is tied to a class: creating the account with the
    homeroom role and an arm makes that teacher the arm's class teacher."""
    from .test_academics import _create_arm, _create_session

    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    arm_id = _create_arm(client, sid, session_id, "JSS 1A")
    staff = _add_staff(client, sid, staff_no="T010")

    r = client.post(
        f"{STAFF}/{staff['id']}/account",
        json={
            "email": "homeroom@test.edu",
            "password": "Str0ng!Pass",
            "role_id": _role_id(client, sid, "homeroom_teacher"),
            "arm_id": arm_id,
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role_code"] == "homeroom_teacher"

    # The staff list reports the class the teacher leads.
    row = next(
        s
        for s in client.get(STAFF, headers={"X-School-Id": sid}).json()
        if s["id"] == staff["id"]
    )
    assert row["homeroom_arm_id"] == arm_id
    assert row["homeroom_arm_name"] == "JSS 1A"


def test_updating_role_to_homeroom_links_and_moves_the_class(client):
    """Promoting an existing account to homeroom teacher links the chosen class,
    and choosing another class in the same session releases the previous one."""
    from .test_academics import _create_arm, _create_session

    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    arm_a = _create_arm(client, sid, session_id, "JSS 2A")
    arm_b = _create_arm(client, sid, session_id, "JSS 2B")
    staff = _add_staff(client, sid, staff_no="T011")
    assert _create_account(client, sid, staff["id"], email="role@test.edu").status_code == 201

    role = _role_id(client, sid, "homeroom_teacher")
    r = client.patch(
        f"{STAFF}/{staff['id']}/account",
        json={"role_id": role, "arm_id": arm_a},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role_code"] == "homeroom_teacher"

    r = client.patch(
        f"{STAFF}/{staff['id']}/account",
        json={"role_id": role, "arm_id": arm_b},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    row = next(
        s
        for s in client.get(STAFF, headers={"X-School-Id": sid}).json()
        if s["id"] == staff["id"]
    )
    assert row["homeroom_arm_id"] == arm_b


def test_staff_list_shows_subject_per_class(client):
    """The same subject is taught by different teachers in different classes;
    the staff list reports each class × subject pair separately."""
    from .test_academics import _create_arm, _create_session

    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    arm_1 = _create_arm(client, sid, session_id, "JSS 1 A")
    arm_2 = _create_arm(client, sid, session_id, "JSS 2 A")
    maths = client.post(
        "/api/academics/subjects",
        json={"name": "Mathematics", "code": "MTH"},
        headers={"X-School-Id": sid},
    ).json()["id"]

    teacher_a = _add_staff(client, sid, staff_no="T020", full_name="Ada Maths")
    teacher_b = _add_staff(client, sid, staff_no="T021", full_name="Bola Maths")

    for staff, arm in ((teacher_a, arm_1), (teacher_b, arm_2)):
        r = client.post(
            "/api/academics/assignments",
            json={"arm_id": arm, "subject_id": maths, "teacher_id": staff["id"]},
            headers={"X-School-Id": sid},
        )
        assert r.status_code == 201, r.text

    listing = client.get(STAFF, headers={"X-School-Id": sid}).json()
    a = next(s for s in listing if s["id"] == teacher_a["id"])
    b = next(s for s in listing if s["id"] == teacher_b["id"])
    assert [(x["subject_name"], x["arm_name"]) for x in a["assignments"]] == [("Mathematics", "JSS 1 A")]
    assert [(x["subject_name"], x["arm_name"]) for x in b["assignments"]] == [("Mathematics", "JSS 2 A")]


def test_account_with_random_role_id_404(client):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T008")
    r = client.post(
        f"{STAFF}/{staff['id']}/account",
        json={"email": "ghost@test.edu", "password": "Str0ng!Pass", "role_id": str(uuid.uuid4())},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"