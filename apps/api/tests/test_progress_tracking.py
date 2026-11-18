"""Student progress tracking: is each pupil improving, and is it a paid feature?

Two things matter and they are tested separately:

  * the **reading** — a direction is claimed only from two or more observations,
    it is the pupil against themselves (never the class), and the basis says
    whether it came from terms or from this term's assessment components;
  * the **gate** — progress tracking is sold separately, so a school without the
    toggle is refused with the premium code before any work is done, even though
    its staff hold every results permission.
"""
import uuid
from datetime import datetime, timezone

from app.models import School
from app.models.results import AssessmentComponent, Result, Score
from app.services import progress_service

from .conftest import active_school_id, register_school
from .test_student_scope import _world

ACAD = "/api/academics"
RESULTS = "/api/results"


def _enable_progress(db, sid: str) -> None:
    school = db.get(School, uuid.UUID(sid))
    school.settings = {**(school.settings or {}), "progress_enabled": True}
    db.flush()


def _enrollment_id(db, sid: str, student_id: str) -> uuid.UUID:
    from app.models import StudentEnrollment

    return db.scalar(
        StudentEnrollment.__table__.select()
        .with_only_columns(StudentEnrollment.id)
        .where(StudentEnrollment.student_id == uuid.UUID(student_id))
    )


def _component(db, sid: str, term_id: str, arm_id: str, name: str, order: int, max_score: float = 20):
    comp = AssessmentComponent(
        school_id=uuid.UUID(sid),
        term_id=uuid.UUID(term_id),
        class_arm_id=uuid.UUID(arm_id),
        name=name,
        max_score=max_score,
        weight=50,
        sort_order=order,
    )
    db.add(comp)
    db.flush()
    return comp


def _score(db, sid: str, enrollment_id, arm_id: str, subject_id: str, component_id, value: float):
    db.add(
        Score(
            school_id=uuid.UUID(sid),
            student_enrollment_id=enrollment_id,
            class_arm_id=uuid.UUID(arm_id),
            subject_id=uuid.UUID(subject_id),
            assessment_component_id=component_id,
            score=value,
            entered_at=datetime.now(timezone.utc),
        )
    )
    db.flush()


def _result(db, sid: str, enrollment_id, arm_id: str, subject_id: str, term_id: str, total: float):
    db.add(
        Result(
            school_id=uuid.UUID(sid),
            student_enrollment_id=enrollment_id,
            subject_id=uuid.UUID(subject_id),
            term_id=uuid.UUID(term_id),
            class_arm_id=uuid.UUID(arm_id),
            status="draft",
            total=total,
        )
    )
    db.flush()


# ── the reading ──────────────────────────────────────────────────────────────

def test_classify_refuses_a_single_observation():
    trend = progress_service.classify([62], basis="terms")
    assert trend.direction == "insufficient"
    assert trend.basis == "none"
    assert trend.samples == 1


def test_classify_reads_the_latest_movement_not_the_whole_average():
    # Rose, then fell: the last movement is what the school needs to see.
    trend = progress_service.classify([40, 70, 58], basis="terms")
    assert trend.direction == "declining"
    assert trend.delta == -12
    assert trend.change == 18


def test_classify_ignores_a_change_inside_the_noise_band():
    assert progress_service.classify([60, 61.5], basis="terms").direction == "steady"
    assert progress_service.classify([60, 62], basis="terms").direction == "improving"
    assert progress_service.classify([60, 58], basis="terms").direction == "declining"


def test_progress_reads_the_current_terms_components_when_only_one_term_exists(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    _enable_progress(db, sid)
    arm = w["arms"]["JSS 1 A"]
    student = w["students"]["JSS 1 A"]
    enrollment = _enrollment_id(db, sid, student)
    first = _component(db, sid, w["term_id"], arm, "1st CA", 1)
    second = _component(db, sid, w["term_id"], arm, "2nd CA", 2)
    # 50% then 80%: the pupil against themselves, improving.
    _score(db, sid, enrollment, arm, w["subject_id"], first.id, 10)
    _score(db, sid, enrollment, arm, w["subject_id"], second.id, 16)

    r = client.get(
        f"{RESULTS}/progress",
        params={"arm_id": arm, "session_id": w["session_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["core_configured"] is False  # nothing flagged: the whole curriculum is tracked
    ada = next(row for row in body["students"] if row["admission_no"] == "A-001")
    subject = ada["subjects"][0]
    assert subject["trend"]["basis"] == "components"
    assert subject["trend"]["direction"] == "improving"
    assert subject["trend"]["delta"] == 30
    assert [run["percent"] for run in subject["components"]["series"]] == [50.0, 80.0]


def test_progress_prefers_terms_once_a_second_term_has_marks(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    _enable_progress(db, sid)
    arm = w["arms"]["JSS 1 A"]
    student = w["students"]["JSS 1 A"]
    enrollment = _enrollment_id(db, sid, student)
    headers = {"X-School-Id": sid}

    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": w["session_id"], "term_no": 2, "name": "Second Term"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    second_term = r.json()["id"]
    _result(db, sid, enrollment, arm, w["subject_id"], w["term_id"], 48)
    _result(db, sid, enrollment, arm, w["subject_id"], second_term, 61)

    r = client.get(
        f"{RESULTS}/progress",
        params={"arm_id": arm, "session_id": w["session_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    ada = next(row for row in r.json()["students"] if row["admission_no"] == "A-001")
    subject = ada["subjects"][0]
    assert subject["trend"]["basis"] == "terms"
    assert subject["trend"]["direction"] == "improving"
    assert subject["trend"]["delta"] == 13
    assert [row["value"] for row in subject["terms"]] == [48.0, 61.0]
    # The class average follows the same two terms.
    assert [row["value"] for row in ada["overall"]["series"]] == [48.0, 61.0]


def test_progress_is_the_pupil_against_themselves_not_the_class(client, db):
    """A pupil who scores 30 then 45 is improving even though another child's 80
    is higher: the comparison is the same child's earlier work."""
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    _enable_progress(db, sid)
    arm = w["arms"]["JSS 1 A"]
    headers = {"X-School-Id": sid}

    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": w["session_id"], "term_no": 2, "name": "Second Term"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    second_term = r.json()["id"]
    for arm_name, totals in (("JSS 1 A", (30, 45)), ("JSS 1 B", (80, 78))):
        enrollment = _enrollment_id(db, sid, w["students"][arm_name])
        _result(db, sid, enrollment, w["arms"][arm_name], w["subject_id"], w["term_id"], totals[0])
        _result(db, sid, enrollment, w["arms"][arm_name], w["subject_id"], second_term, totals[1])

    r = client.get(f"{RESULTS}/progress", params={"arm_id": arm, "session_id": w["session_id"]}, headers=headers)
    assert r.status_code == 200, r.text
    ada = next(row for row in r.json()["students"] if row["admission_no"] == "A-001")
    assert ada["subjects"][0]["trend"]["direction"] == "improving"
    assert ada["subjects"][0]["latest"] == 45.0

    r = client.get(
        f"{RESULTS}/progress",
        params={"arm_id": w["arms"]["JSS 1 B"], "session_id": w["session_id"]},
        headers=headers,
    )
    other = next(row for row in r.json()["students"] if row["admission_no"] == "B-001")
    # …and the higher score in the other class is *declining*: 80 → 78.
    assert other["subjects"][0]["trend"]["direction"] == "declining"
    assert other["subjects"][0]["latest"] == 78.0


# ── the gate ─────────────────────────────────────────────────────────────────

def test_progress_is_refused_without_the_premium_toggle(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)

    r = client.get(
        f"{RESULTS}/progress",
        params={"arm_id": w["arms"]["JSS 1 A"], "session_id": w["session_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "ERR_PREMIUM_REQUIRED"


def test_the_platform_admin_can_turn_it_on(client, db):
    """The toggle is Clearis's, not the school's — it is a billing switch."""
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)

    r = client.patch(
        f"/api/platform/schools/{sid}/progress", json={"enabled": True}
    )
    # The founding school admin is not a platform admin, so this is refused…
    assert r.status_code in (403, 404), r.text

    # …and the server-side toggle is what actually opens the feature.
    _enable_progress(db, sid)
    r = client.get(
        f"{RESULTS}/progress",
        params={"arm_id": w["arms"]["JSS 1 A"], "session_id": w["session_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text