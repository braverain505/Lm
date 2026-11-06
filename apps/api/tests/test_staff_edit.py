"""Editing a staff member's own details.

The edit form sends every field it shows, blank ones included, so a school that
never recorded a phone number or an email still posts those keys as empty
strings. A blank optional field means "nothing on file", not a malformed value,
so it saves as a clear rather than failing the request.
"""
from .conftest import active_school_id, register_school

STAFF = "/api/staff"


def _add_staff(
    client, school_id: str, *, staff_no: str, full_name: str = "Grace Teacher", email: str | None = None
) -> dict:
    body: dict = {
        "staff_no": staff_no,
        "full_name": full_name,
        "membership_type": "teaching",
    }
    if email is not None:
        body["email"] = email
    r = client.post(STAFF, json=body, headers={"X-School-Id": school_id})
    assert r.status_code == 201, r.text
    return r.json()


def _edit(client, school_id: str, staff_id: str, **fields):
    return client.patch(
        f"{STAFF}/{staff_id}", json=fields, headers={"X-School-Id": school_id}
    )


def test_a_name_edit_saves_when_the_other_fields_are_left_blank(client):
    """The form posts blank phone, email and gender for a staff member with
    none on file. Renaming them must still save."""
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T100")

    r = _edit(
        client, sid, staff["id"],
        full_name="Grace Okafor", phone="", email="", gender="",
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Grace Okafor"
    assert body["email"] is None
    assert body["phone"] is None

    # And the rename is on the roster, not just in the response.
    listed = client.get(STAFF, headers={"X-School-Id": sid}).json()
    assert next(s for s in listed if s["id"] == staff["id"])["full_name"] == "Grace Okafor"


def test_a_name_edit_saves_when_every_box_is_filled_in(client):
    """The same form with a full record in it — including the gender, which the
    schema used to drop on the floor."""
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T106", email="grace@test.edu")

    r = _edit(
        client, sid, staff["id"],
        full_name="Grace Okafor", phone="080 1234 5678",
        email="grace@test.edu", gender="female",
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Grace Okafor"
    assert body["phone"] == "080 1234 5678"
    assert body["email"] == "grace@test.edu"
    assert body["gender"] == "female"


def test_editing_a_staff_members_gender_saves(client):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T101")

    r = _edit(client, sid, staff["id"], gender="female")
    assert r.status_code == 200, r.text
    assert r.json()["gender"] == "female"


def test_clearing_a_recorded_email_and_phone_clears_them(client):
    """A field emptied on purpose is a clear, not a no-op — the school is
    saying there is no such contact detail on file."""
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T102", email="grace@test.edu")

    r = _edit(client, sid, staff["id"], email="", phone="080 0000 0000")
    assert r.status_code == 200, r.text
    assert r.json()["email"] is None
    assert r.json()["phone"] == "080 0000 0000"

    r = _edit(client, sid, staff["id"], phone="")
    assert r.status_code == 200, r.text
    assert r.json()["phone"] is None


def test_a_field_the_form_does_not_send_is_left_alone(client):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T103", email="grace@test.edu", full_name="Grace Teacher")

    r = _edit(client, sid, staff["id"], full_name="Grace Okafor")
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "grace@test.edu"


def test_a_blank_name_is_refused(client):
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T104")

    for blank in ("", "   "):
        r = _edit(client, sid, staff["id"], full_name=blank)
        assert r.status_code == 422, r.text
    listed = client.get(STAFF, headers={"X-School-Id": sid}).json()
    assert next(s for s in listed if s["id"] == staff["id"])["full_name"] == "Grace Teacher"


def test_a_malformed_email_is_still_refused(client):
    """Blank is a clear; something that is not an address at all is an error."""
    register_school(client)
    sid = active_school_id(client)
    staff = _add_staff(client, sid, staff_no="T105")

    r = _edit(client, sid, staff["id"], email="not-an-email")
    assert r.status_code == 422, r.text
