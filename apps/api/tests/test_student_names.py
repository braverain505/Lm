"""A pupil with three name parts must be editable part by part.

The edit form used to carry only first and last name, so a child recorded as
"Markus Jinnatabi Biyaya" could never have their middle name changed — the field
holding it was not on the form at all. Worse, clearing a part did nothing: the
schema turns an emptied string into ``None``, and the service skipped every
``None``, so the old name came straight back. These tests pin both halves.

They also pin the rule that makes clearing safe: a field the caller did **not**
send is left alone, so saving one part never blanks another.
"""
from .conftest import active_school_id, register_school

STUDENTS = "/api/students"


def _create(client, sid: str, **name) -> dict:
    payload = {
        "admission_no": "N-001",
        "gender": "male",
        **name,
    }
    r = client.post(STUDENTS, json=payload, headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    return r.json()


def test_three_part_name_is_stored_and_edited_part_by_part(client, db):
    register_school(client)
    sid = active_school_id(client)
    headers = {"X-School-Id": sid}
    student = _create(client, sid, first_name="Markus", middle_name="Jinnatabi", last_name="Biyaya")
    assert student["full_name"] == "Markus Jinnatabi Biyaya"

    r = client.patch(
        f"{STUDENTS}/{student['id']}", json={"middle_name": "Chidi"}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Markus Chidi Biyaya"

    # A word can be moved out of the field it was typed into.
    r = client.patch(
        f"{STUDENTS}/{student['id']}",
        json={"first_name": "Markus Lee", "middle_name": "Jinnatabi"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Markus Lee Jinnatabi Biyaya"


def test_clearing_the_middle_name_actually_clears_it(client, db):
    register_school(client)
    sid = active_school_id(client)
    headers = {"X-School-Id": sid}
    student = _create(client, sid, first_name="Markus", middle_name="Jinnatabi", last_name="Biyaya")

    r = client.patch(f"{STUDENTS}/{student['id']}", json={"middle_name": ""}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["middle_name"] is None
    assert body["full_name"] == "Markus Biyaya"


def test_a_field_that_is_not_sent_is_not_cleared(client, db):
    """Saving one part must not blank the others — the form sends only what changed."""
    register_school(client)
    sid = active_school_id(client)
    headers = {"X-School-Id": sid}
    student = _create(client, sid, first_name="Markus", middle_name="Jinnatabi", last_name="Biyaya")

    r = client.patch(f"{STUDENTS}/{student['id']}", json={"first_name": "Mark"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Mark Jinnatabi Biyaya"


def test_a_required_part_cannot_be_blanked(client, db):
    """An emptied first name would leave a pupil with no name — refused, not stored."""
    register_school(client)
    sid = active_school_id(client)
    headers = {"X-School-Id": sid}
    student = _create(client, sid, first_name="Markus", middle_name="Jinnatabi", last_name="Biyaya")

    r = client.patch(f"{STUDENTS}/{student['id']}", json={"first_name": ""}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["first_name"] == "Markus"