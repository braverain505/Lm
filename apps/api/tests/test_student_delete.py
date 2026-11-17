"""Deleting a pupil must take them out of the class, not just flag the record.

The flag alone left the work half-done and the child still in front of the
teacher: the enrollment stayed current and active, and the class roster, the
attendance roster and the score grid all read enrollments. El Gibbor Academy
deleted pupils and watched them stay put in their classes.

Two behaviours the fix must not break, both pinned below:

  * a **promoted** pupil is still returned to results work for the term they sat
    — their enrollment is completed, not deleted, and a term reopened for
    correction must still show them;
  * marks already recorded are **kept** when a pupil is deleted. Deleting the
    enrollment row would cascade them away, and a delete button should not
    silently destroy a term of a teacher's work.
"""
import uuid

from sqlalchemy import select

from app.models import Score, Student, StudentEnrollment
from app.services import people_service

from .conftest import active_school_id, grant_permission, register_school
from .test_student_scope import _world

STUDENTS = "/api/students"
RESULTS = "/api/results"


def _enter_one_mark(client, db, sid: str, w: dict, arm_name: str) -> None:
    """Record a mark for that arm's pupil, through the API a teacher uses."""
    headers = {"X-School-Id": sid}
    grant_permission(db, sid, "results.enter")
    arm_id = w["arms"][arm_name]
    r = client.get(
        f"{RESULTS}/components",
        params={"term_id": w["term_id"], "arm_id": arm_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    component_id = r.json()[0]["id"]
    enrollment_id = db.scalar(
        select(StudentEnrollment.id).where(
            StudentEnrollment.student_id == w["students"][arm_name]
        )
    )
    r = client.put(
        f"{RESULTS}/scorecard",
        json={
            "arm_id": arm_id,
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": str(enrollment_id),
                    "scores": [
                        {"assessment_component_id": component_id, "score": 15}
                    ],
                }
            ],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_deleting_a_pupil_removes_them_from_class_roster_and_grid(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    headers = {"X-School-Id": sid}
    arm_a = w["arms"]["JSS 1 A"]
    student_a = w["students"]["JSS 1 A"]
    _enter_one_mark(client, db, sid, w, "JSS 1 A")

    roster = client.get(f"{STUDENTS}/arms/{arm_a}/enrollments", headers=headers)
    assert roster.status_code == 200 and len(roster.json()) == 1, roster.text
    grid = client.get(
        f"{RESULTS}/scorecard",
        params={"arm_id": arm_a, "subject_id": w["subject_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert [row["full_name"] for row in grid.json()["students"]] == ["Ada Alpha"]

    r = client.delete(f"{STUDENTS}/{student_a}", headers=headers)
    assert r.status_code == 204, r.text

    # The class no longer lists them, on the roster or in the grid.
    roster = client.get(f"{STUDENTS}/arms/{arm_a}/enrollments", headers=headers)
    assert roster.status_code == 200 and roster.json() == [], roster.text
    grid = client.get(
        f"{RESULTS}/scorecard",
        params={"arm_id": arm_a, "subject_id": w["subject_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert grid.status_code == 200 and grid.json()["students"] == [], grid.text

    # The record is flagged, the enrollment is closed, and the mark survives.
    assert db.scalar(select(Student.is_deleted).where(Student.id == student_a)) is True
    enrollment = db.scalar(
        select(StudentEnrollment).where(StudentEnrollment.student_id == student_a)
    )
    assert enrollment.status == "withdrawn"
    assert enrollment.is_current is False
    assert db.scalar(select(Score).where(Score.student_enrollment_id == enrollment.id)) is not None


def test_the_other_class_is_untouched(client, db):
    """Deleting one pupil must not sweep the class next door."""
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    headers = {"X-School-Id": sid}

    r = client.delete(f"{STUDENTS}/{w['students']['JSS 1 A']}", headers=headers)
    assert r.status_code == 204, r.text

    roster = client.get(f"{STUDENTS}/arms/{w['arms']['JSS 1 B']}/enrollments", headers=headers)
    assert roster.status_code == 200 and len(roster.json()) == 1, roster.text


def test_a_promoted_pupil_is_still_shown_to_results_work(client, db):
    """The fix must not hide a pupil who merely moved on.

    ``include_inactive`` is what the score grid and the report-card index ask
    for, so a term can be corrected after its pupils were promoted. A completed
    enrollment is not a deletion, and must keep appearing.
    """
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    arm_a = w["arms"]["JSS 1 A"]
    student_a = w["students"]["JSS 1 A"]

    enrollment = db.scalar(
        select(StudentEnrollment).where(StudentEnrollment.student_id == student_a)
    )
    enrollment.status = "completed"
    enrollment.is_current = False
    db.flush()

    school_id = uuid.UUID(sid)
    assert [e.id for e in people_service.list_enrollments(db, school_id, arm_a, include_inactive=True)] == [
        enrollment.id
    ]
    # The plain roster, which is what a current class list asks for, drops them.
    assert people_service.list_enrollments(db, school_id, arm_a) == []

    # Deleting is what takes them out of results work as well.
    r = client.delete(f"{STUDENTS}/{student_a}", headers={"X-School-Id": sid})
    assert r.status_code == 204, r.text
    assert people_service.list_enrollments(db, school_id, arm_a, include_inactive=True) == []
