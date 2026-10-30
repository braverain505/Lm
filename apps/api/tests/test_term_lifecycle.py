"""Term lifecycle tests: reopening a closed term for a correction.

Reopening is a school's error path after sign-off. These tests pin the contract:
published cards are archived before anything is touched, the term's results
return to draft, scores can be edited and compiled again, and the archive keeps
the exact document a parent already had. The third case pins the per-school
final-term policy that adds the combined term average to the last card.
"""
import uuid

from sqlalchemy import select

from app.models import Result, ResultEvent, StudentEnrollment, Term, TermResultArchive
from .conftest import active_school_id, register_school
from .test_results import (
    ACAD,
    BASE,
    _act,
    _add_components,
    _configure,
    _enter_and_publish,
    _first_student_id,
)

SCHOOLS = "/api/schools"


def _open_term(client, sid: str, session_id: str, term_no: int, name: str) -> str:
    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": session_id, "term_no": term_no, "name": name},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    term_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/terms/{term_id}/activate", headers={"X-School-Id": sid}
    )
    assert r.status_code == 200, r.text
    return term_id


def test_reopening_a_closed_term_archives_cards_and_unlocks_scores(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_and_publish(client, sid, w, comps, score=60)

    r = client.post(f"{ACAD}/terms/{w['term_id']}/close", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"

    # Closing itself freezes the published cards — the archive is the record of
    # every completed term, not only of corrections.
    db.expire_all()
    at_close = db.scalars(select(TermResultArchive)).all()
    assert len(at_close) == 1
    assert at_close[0].student_count == 3
    assert "closed" in at_close[0].reason.lower()

    # A closed term refuses scores — the state the school hits when an error is
    # found after the cards went out.
    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": w["enrollment_ids"][0],
                    "scores": [
                        {"assessment_component_id": comps["CA1"], "score": 90}
                    ],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422

    r = client.post(
        f"{ACAD}/terms/{w['term_id']}/reopen",
        json={"reason": "Aisha's CA score was entered under the wrong student"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["archive_version"] == 1
    assert body["archive_id"] is not None
    assert body["results_reset"] == 3
    assert body["term"]["status"] == "open"
    assert body["term"]["is_current"] is True

    db.expire_all()
    # The live rows are editable again, and the old published snapshots are no
    # longer the current record.
    results = db.scalars(
        select(Result).where(Result.term_id == uuid.UUID(w["term_id"]))
    ).all()
    assert len(results) == 3
    assert all(row.status == "draft" for row in results)
    assert all(row.published_snapshot is None for row in results)
    term = db.get(Term, uuid.UUID(w["term_id"]))
    assert term.status == "open" and term.is_current is True

    # The archive captured the exact cards that were live before the reopen.
    archives = db.scalars(select(TermResultArchive)).all()
    assert len(archives) == 1
    archive = archives[0]
    assert archive.student_count == 3
    assert archive.class_count == 1
    assert archive.version == 1
    # Reopening reuses the archive closing already wrote rather than storing
    # the same cards twice; the correction reason lives on the result events.
    assert "closed" in archive.reason.lower()

    r = client.get(f"{BASE}/archives", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(archive.id)
    assert rows[0]["term_name"] == "First Term"
    assert rows[0]["session_name"] == "2025/2026"
    assert rows[0]["student_count"] == 3
    assert rows[0]["version"] == 1

    r = client.get(
        f"{BASE}/archives/{archive.id}", headers={"X-School-Id": sid}
    )
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["payload"]["term"]["name"] == "First Term"
    assert detail["payload"]["layout"]["widgets"]
    frozen = detail["payload"]["students"]
    assert len(frozen) == 3
    assert frozen[0]["subjects"][0]["total"] == 60.0

    # Edit the score that was wrong, then compile the term again.
    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": w["enrollment_ids"][0],
                    "scores": [
                        {"assessment_component_id": comps["CA1"], "score": 90}
                    ],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    for step in ("submit", "verify", "approve", "publish"):
        r = _act(client, sid, w, step)
        assert r.status_code == 200, (step, r.text)

    # Read the card of the student whose CA was corrected, not merely the first
    # enrollment by id (which is a different student).
    edited = db.get(StudentEnrollment, uuid.UUID(w["enrollment_ids"][0]))
    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": str(edited.student_id), "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    # CA1 90, CA2 60, Exam 60 at 20/30/50 → 66.0
    assert r.json()["subjects"][0]["total"] == 66.0

    # Reopening is journaled against every result it unlocked.
    reopen_events = db.scalars(
        select(ResultEvent).where(ResultEvent.action == "reopen")
    ).all()
    assert len(reopen_events) == 3
    assert all(event.note and "wrong student" in event.note for event in reopen_events)


def test_reopen_requires_a_closed_term_and_a_reason(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)

    # An open term is not reopened — closing is what sign-off means.
    r = client.post(
        f"{ACAD}/terms/{w['term_id']}/reopen",
        json={"reason": "Trying to reopen an open term"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    assert "closed" in r.json()["error"]["message"].lower()

    r = client.post(
        f"{ACAD}/terms/{w['term_id']}/close", headers={"X-School-Id": sid}
    )
    assert r.status_code == 200, r.text

    # The reason is required and must say something useful.
    r = client.post(
        f"{ACAD}/terms/{w['term_id']}/reopen",
        json={"reason": "x"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"

    r = client.post(
        f"{ACAD}/terms/{w['term_id']}/reopen",
        json={"reason": "Correcting a transposed score"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text


def test_reopened_term_keeps_its_students_after_promotion(client, db):
    """A term corrected after promotion must still see its own students.

    Promotion closes the old enrollments (``is_current=False``,
    ``status='completed'``). The score grid, report-card index and bulk cards
    for the reopened term are keyed by the arm, not by the current roster, so
    the school can actually fix the result it came back to.
    """
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_and_publish(client, sid, w, comps, score=60)
    assert client.post(
        f"{ACAD}/terms/{w['term_id']}/close", headers={"X-School-Id": sid}
    ).status_code == 200

    # Simulate promotion of the whole class into the next session.
    db.expire_all()
    enrollments = db.scalars(
        select(StudentEnrollment).where(
            StudentEnrollment.class_arm_id == uuid.UUID(w["arm_id"])
        )
    ).all()
    assert len(enrollments) == 3
    for enrollment in enrollments:
        enrollment.is_current = False
        enrollment.status = "completed"
    db.flush()

    r = client.post(
        f"{ACAD}/terms/{w['term_id']}/reopen",
        json={"reason": "Correcting a result after promotion"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"{BASE}/scorecard",
        params={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["students"]) == 3

    r = client.get(
        f"{BASE}/report-index",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 3

    # The normal compile path still produces printable cards for the class.
    for step in ("submit", "verify", "approve", "publish"):
        r = _act(client, sid, w, step)
        assert r.status_code == 200, (step, r.text)
    r = client.get(
        f"{BASE}/report-cards",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 3


def test_final_term_card_combines_term_averages_when_policy_is_on(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)  # First Term, activated
    comps = _add_components(client, sid, w["term_id"])
    _enter_and_publish(client, sid, w, comps, score=60)

    second = _open_term(client, sid, w["session_id"], 2, "Second Term")
    second_comps = _add_components(client, sid, second)
    _enter_and_publish(
        client, sid, {**w, "term_id": second}, second_comps, score=70
    )

    third = _open_term(client, sid, w["session_id"], 3, "Third Term")
    third_comps = _add_components(client, sid, third)
    _enter_and_publish(
        client, sid, {**w, "term_id": third}, third_comps, score=80
    )

    student_id = _first_student_id(db, w["arm_id"])

    def card(term_id: str) -> dict:
        r = client.get(
            f"{BASE}/report-card",
            params={"student_id": student_id, "term_id": term_id},
            headers={"X-School-Id": sid},
        )
        assert r.status_code == 200, r.text
        return r.json()

    # Default: the final term card is a normal term card.
    assert card(third)["cumulative"] is None

    r = client.patch(
        f"{SCHOOLS}/me/results-policy",
        json={"combine_previous_terms": True, "final_term_no": 3},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"combine_previous_terms": True, "final_term_no": 3}

    final = card(third)["cumulative"]
    assert final is not None
    assert final["final_term_no"] == 3
    assert [row["average"] for row in final["terms"]] == [60.0, 70.0, 80.0]
    assert final["session_average"] == 70.0
    assert final["term_average"] == 80.0
    # Per-subject session average is the mean of the three term totals.
    assert final["subjects"][0]["subject_name"] == "Mathematics"
    assert [row["total"] for row in final["subjects"][0]["terms"]] == [
        60.0,
        70.0,
        80.0,
    ]
    assert final["subjects"][0]["average"] == 70.0

    # Only the configured final term carries the block.
    assert card(second)["cumulative"] is None

    # Switching the policy off removes it again, without touching the results.
    r = client.patch(
        f"{SCHOOLS}/me/results-policy",
        json={"combine_previous_terms": False, "final_term_no": 3},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert card(third)["cumulative"] is None
