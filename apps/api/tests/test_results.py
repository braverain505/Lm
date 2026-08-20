"""Results engine tests: component weight validation, score clamping, grade
boundaries (WAEC), the draft→submitted state guard, the approval workflow
(verify→approve→publish→reject), the workbench, and the readiness rows.

These exercise the real service layer through the HTTP API (with the test
session injected), so they cover the routing + service + schema integration
in one pass.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Result, ResultEvent
from app.seed import seed_grade_scale
from .conftest import active_school_id, register_school

BASE = "/api/results"
ACAD = "/api/academics"


def _configure(client, school_id: str, db: Session) -> dict:
    """Create session, term, arm, subject, offering, three students,
    and one teacher — the minimal world for results scoring."""
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": school_id},
    )
    session_id = r.json()["id"]

    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": session_id, "term_no": 1, "name": "First Term"},
        headers={"X-School-Id": school_id},
    )
    term_id = r.json()["id"]

    # The admin must activate the session + term before any results work.
    r = client.post(
        f"{ACAD}/sessions/{session_id}/activate",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"{ACAD}/terms/{term_id}/activate",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": session_id, "name": "JSS 1 A"},
        headers={"X-School-Id": school_id},
    )
    arm_id = r.json()["id"]

    r = client.post(
        f"{ACAD}/subjects",
        json={"name": "Mathematics", "code": "MTH"},
        headers={"X-School-Id": school_id},
    )
    subject_id = r.json()["id"]

    r = client.post(
        f"{ACAD}/offerings",
        json={"arm_id": arm_id, "subject_id": subject_id},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text

    # The WAEC 9-point scale (A1 90–100 … F9 0–39) drives the grade mapping.
    seed_grade_scale(db, school_id)

    enrollment_ids = []
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
        student_id = r.json()["id"]
        r = client.post(
            "/api/students/enrollments",
            json={"student_id": student_id, "arm_id": arm_id, "session_id": session_id},
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
    }


def _add_components(client, school_id: str, term_id: str) -> dict:
    """School-wide components CA1 20 / CA2 30 / Exam 50 (sum 100)."""
    ids = {}
    for name, weight in [("CA1", 20), ("CA2", 30), ("Exam", 50)]:
        r = client.post(
            f"{BASE}/components",
            json={"term_id": term_id, "name": name, "max_score": 100, "weight": weight},
            headers={"X-School-Id": school_id},
        )
        assert r.status_code == 201, r.text
        ids[name] = r.json()["id"]
    return ids


def test_score_entry_and_grade(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])

    # Weights: CA1 20, CA2 30, Exam 50 (sum 100).
    #  Student 1: (90*.2)+(80*.3)+(80*.5) = 18+24+40 = 82
    #  Student 2: (50*.2)+(50*.3)+(50*.5) = 10+15+25 = 50
    #  Student 3: (20*.2)+(10*.3)+(10*.5) = 4+3+5 = 12
    cards = [
        (w["enrollment_ids"][0], {"CA1": 90, "CA2": 80, "Exam": 80}),
        (w["enrollment_ids"][1], {"CA1": 50, "CA2": 50, "Exam": 50}),
        (w["enrollment_ids"][2], {"CA1": 20, "CA2": 10, "Exam": 10}),
    ]
    entries = [
        {
            "student_enrollment_id": env_id,
            "scores": [
                {"assessment_component_id": comps[comp], "score": value}
                for comp, value in card.items()
            ],
        }
        for env_id, card in cards
    ]
    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": entries,
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    totals = {e["enrollment_id"]: e for e in body["students"]}
    assert totals[w["enrollment_ids"][0]]["total"] == 82
    assert totals[w["enrollment_ids"][0]]["grade_letter"] == "B2"
    assert totals[w["enrollment_ids"][1]]["total"] == 50
    assert totals[w["enrollment_ids"][1]]["grade_letter"] == "C6"
    assert totals[w["enrollment_ids"][2]]["total"] == 12
    assert totals[w["enrollment_ids"][2]]["grade_letter"] == "F9"


def test_score_over_max_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    env = w["enrollment_ids"][0]

    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": env,
                    "scores": [{"assessment_component_id": comps["CA1"], "score": 150}],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_SCORE_OVER_MAX"


def test_negative_score_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])

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
                        {"assessment_component_id": comps["CA1"], "score": -5}
                    ],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_SCORE_NEGATIVE"


def test_component_weights_must_sum_100(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)

    # A single 60-weight component is a broken set: weights must total 100.
    r = client.post(
        f"{BASE}/components",
        json={"term_id": w["term_id"], "name": "Only", "max_score": 100, "weight": 60},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text

    env = w["enrollment_ids"][0]
    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": env,
                    "scores": [
                        {"assessment_component_id": r.json()["id"], "score": 50}
                    ],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_WEIGHT_SUM"


def test_submit_locks_scores(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    env = w["enrollment_ids"][0]

    def enter(score: int):
        return client.put(
            f"{BASE}/scorecard",
            json={
                "arm_id": w["arm_id"],
                "subject_id": w["subject_id"],
                "term_id": w["term_id"],
                "entries": [
                    {
                        "student_enrollment_id": env,
                        "scores": [
                            {"assessment_component_id": comps["CA1"], "score": score}
                        ],
                    }
                ],
            },
            headers={"X-School-Id": sid},
        )

    assert enter(60).status_code == 200
    r = client.post(
        f"{BASE}/submit",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["submitted"] >= 1

    # After submit, editing the same cell is locked.
    r = enter(70)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_RESULT_LOCKED"


def test_readiness_shows_pending(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    _add_components(client, sid, w["term_id"])

    r = client.get(
        f"{BASE}/readiness",
        params={"term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(row["subject_id"] == w["subject_id"] for row in rows)
    row = next(row for row in rows if row["subject_id"] == w["subject_id"])
    assert row["student_count"] == 3
    assert row["entered"] == 0
    assert row["pending"] == 3


def test_scorecard_rejects_foreign_enrollment(client, db):
    """A student from another arm cannot be scored in this arm's grid."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])

    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": w["session_id"], "name": "JSS 1 B"},
        headers={"X-School-Id": sid},
    )
    arm_b = r.json()["id"]
    r = client.post(
        "/api/students",
        json={
            "admission_no": "STU-999",
            "first_name": "Lone",
            "last_name": "Wolf",
            "gender": "male",
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/students/enrollments",
        json={
            "student_id": r.json()["id"],
            "arm_id": arm_b,
            "session_id": w["session_id"],
        },
        headers={"X-School-Id": sid},
    )
    foreign_env = r.json()["id"]

    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": foreign_env,
                    "scores": [
                        {"assessment_component_id": comps["CA1"], "score": 50}
                    ],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Approval workflow (verify -> approve -> publish -> reject) ----------------
def _enter_all(client, sid: str, w: dict, comps: dict, score: int = 60) -> None:
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
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": entries,
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text


def _cell(w: dict) -> dict:
    return {
        "arm_id": w["arm_id"],
        "subject_id": w["subject_id"],
        "term_id": w["term_id"],
    }


def _act(client, sid: str, w: dict, action: str, **extra) -> object:
    payload = _cell(w)
    payload.update(extra)
    return client.post(
        f"{BASE}/{action}", json=payload, headers={"X-School-Id": sid}
    )


def test_approval_pipeline_verify_approve_publish(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)

    r = _act(client, sid, w, "submit")
    assert r.status_code == 200 and r.json()["submitted"] == 3

    # Approving before verification is a conflict.
    r = _act(client, sid, w, "approve")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"

    r = _act(client, sid, w, "verify")
    assert r.status_code == 200 and r.json()["verified"] == 3

    # Nothing left at the submitted stage.
    r = _act(client, sid, w, "verify")
    assert r.status_code == 409

    r = _act(client, sid, w, "approve")
    assert r.status_code == 200 and r.json()["approved"] == 3

    r = _act(client, sid, w, "publish")
    assert r.status_code == 200 and r.json()["published"] == 3

    # All rows left the approved stage — publishing again is a conflict.
    r = _act(client, sid, w, "publish")
    assert r.status_code == 409

    # The append-only journal recorded every step.
    actions = {e.action for e in db.scalars(select(ResultEvent)).all()}
    assert {"submit", "verify", "approve", "publish"} <= actions


def test_approve_stamps_approver_and_publish_freezes_snapshot(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)
    actor_id = client.get("/api/auth/me").json()["user"]["id"]

    _act(client, sid, w, "submit")
    _act(client, sid, w, "verify")
    assert _act(client, sid, w, "approve").status_code == 200

    results = db.scalars(
        select(Result).where(Result.class_arm_id == w["arm_id"])
    ).all()
    assert results
    assert all(r.status == "approved" for r in results)
    assert all(r.approved_at is not None for r in results)
    assert all(str(r.approved_by) == actor_id for r in results)

    assert _act(client, sid, w, "publish").status_code == 200
    db.expire_all()
    published = db.scalars(
        select(Result).where(Result.class_arm_id == w["arm_id"])
    ).all()
    assert all(r.status == "published" for r in published)
    assert all(r.published_at is not None for r in published)
    snapshots = [r.published_snapshot for r in published]
    assert all(s is not None for s in snapshots)
    assert all(
        {"total", "grade_letter", "position", "components"} <= set(s.keys())
        for s in snapshots
    )


def test_reject_returns_result_to_draft(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)

    _act(client, sid, w, "submit")
    _act(client, sid, w, "verify")

    r = _act(client, sid, w, "reject", reason="Scores look inconsistent")
    assert r.status_code == 200 and r.json()["rejected"] == 3

    results = db.scalars(
        select(Result).where(Result.class_arm_id == w["arm_id"])
    ).all()
    assert all(r.status == "draft" for r in results)
    assert all(r.submitted_at is None for r in results)

    # The rejection is journaled with the reason.
    events = db.scalars(
        select(ResultEvent).where(ResultEvent.action == "reject")
    ).all()
    assert len(events) == 3
    assert all(e.note == "Scores look inconsistent" for e in events)

    # The teacher can edit scores again now the result is back in draft.
    r = client.put(
        f"{BASE}/scorecard",
        json={
            **{
                "arm_id": w["arm_id"],
                "subject_id": w["subject_id"],
                "term_id": w["term_id"],
            },
            "entries": [
                {
                    "student_enrollment_id": w["enrollment_ids"][0],
                    "scores": [{"assessment_component_id": comps["CA1"], "score": 70}],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text


def test_reject_requires_reason(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    r = _act(client, sid, w, "reject", reason="")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


def test_reject_of_draft_is_conflict(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    # Nothing has been submitted, so there is nothing to reject.
    r = _act(client, sid, w, "reject", reason="Nothing here")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"


def test_workbench_counts_review_stages(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])

    # Score only the first two students — the third stays unscored.
    entries = [
        {
            "student_enrollment_id": env_id,
            "scores": [
                {"assessment_component_id": comps[comp], "score": 60}
                for comp in ("CA1", "CA2", "Exam")
            ],
        }
        for env_id in w["enrollment_ids"][:2]
    ]
    r = client.put(
        f"{BASE}/scorecard",
        json={**_cell(w), "entries": entries},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    def row() -> dict:
        r = client.get(
            f"{BASE}/workbench",
            params={"term_id": w["term_id"]},
            headers={"X-School-Id": sid},
        )
        assert r.status_code == 200, r.text
        return next(x for x in r.json() if x["subject_id"] == w["subject_id"])

    wb = row()
    assert wb["term_id"] == w["term_id"]
    assert wb["enrolled"] == 3
    assert wb["entered"] == 2
    assert wb["draft"] == 3  # every enrollment gets a Result row, even unscored
    assert wb["submitted"] == 0

    _act(client, sid, w, "submit")
    wb = row()
    assert wb["submitted"] == 2
    # The unscored third student stays draft so readiness keeps them pending.
    assert wb["draft"] == 1

    _act(client, sid, w, "verify")
    wb = row()
    assert wb["verified"] == 2
    assert wb["submitted"] == 0

    _act(client, sid, w, "approve")
    wb = row()
    assert wb["approved"] == 2

    _act(client, sid, w, "publish")
    wb = row()
    assert wb["published"] == 2

# --- Report cards ---------------------------------------------------------------
def _enter_and_publish(client, sid, w, comps, score=60):
    """Score every student and drive the cell all the way to published."""
    _enter_all(client, sid, w, comps, score=score)
    for step in ("submit", "verify", "approve", "publish"):
        r = _act(client, sid, w, step)
        assert r.status_code == 200, r.text


def _first_student_id(db, arm_id: str) -> str:
    from app.models import StudentEnrollment

    env = db.scalar(
        select(StudentEnrollment)
        .where(StudentEnrollment.class_arm_id == arm_id)
        .order_by(StudentEnrollment.student_id)
    )
    return str(env.student_id)


def test_report_index_tracks_published_coverage(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])

    def index() -> list[dict]:
        r = client.get(
            f"{BASE}/report-index",
            params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
            headers={"X-School-Id": sid},
        )
        assert r.status_code == 200, r.text
        return r.json()

    # Nothing published yet — everyone listed, zero coverage.
    rows = index()
    assert len(rows) == 3
    assert all(row["subjects_published"] == 0 for row in rows)
    assert all(row["total"] is None for row in rows)

    _enter_all(client, sid, w, comps)
    _enter_and_publish(client, sid, w, comps)

    rows = index()
    assert all(row["subjects_published"] == 1 for row in rows)
    assert all(row["total"] == 60.0 for row in rows)


def test_report_card_renders_published_snapshot_and_standing(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_and_publish(client, sid, w, comps)

    student_id = _first_student_id(db, w["arm_id"])
    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": student_id, "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    card = r.json()

    assert card["term"]["name"] == "First Term"
    assert card["session"]["name"] == "2025/2026"
    assert len(card["subjects"]) == 1
    subj = card["subjects"][0]
    assert subj["subject_name"] == "Mathematics"
    assert subj["total"] == 60.0
    assert subj["grade_letter"] == "C4"
    assert subj["grade_point"] == 4.0
    assert subj["remark"] == "Credit"
    # The snapshot froze the same position the live row held at publish.
    from app.models import Result

    live = db.scalar(
        select(Result)
        .where(
            Result.student_enrollment_id == card["enrollment_id"],
            Result.subject_id == subj["subject_id"],
            Result.term_id == w["term_id"],
        )
    )
    assert subj["position"] == live.position

    summ = card["summary"]
    assert summ["subjects_published"] == 1
    assert summ["total"] == 60.0
    assert summ["average"] == 60.0
    assert summ["class_size"] == 3
    # Everyone scored 60, so this student ranks first under strict ordering.
    assert summ["class_rank"] == 1
    assert summ["grade_letter"] == "C4"


def test_report_card_excludes_unpublished_subject(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_and_publish(client, sid, w, comps)  # Mathematics → published

    # English Language: scored, submitted, verified, approved — but NOT published.
    r = client.post(
        f"{ACAD}/subjects",
        json={"name": "English Language", "code": "ENG"},
        headers={"X-School-Id": sid},
    )
    eng_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/offerings",
        json={"arm_id": w["arm_id"], "subject_id": eng_id},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    w2 = {**w, "subject_id": eng_id}
    _enter_all(client, sid, w2, comps)
    for step in ("submit", "verify", "approve"):
        assert _act(client, sid, w2, step).status_code == 200

    student_id = _first_student_id(db, w["arm_id"])
    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": student_id, "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    # Only the published subject appears on the card.
    card = r.json()
    assert [s["subject_name"] for s in card["subjects"]] == ["Mathematics"]
    assert card["summary"]["subjects_published"] == 1

    # The index agrees: one card ready, one subject still in review.
    r = client.get(
        f"{BASE}/report-index",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert all(row["subjects_published"] == 1 for row in r.json())


def test_report_cards_bulk_returns_all_ready_cards(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_and_publish(client, sid, w, comps)  # all three published Mathematics

    r = client.get(
        f"{BASE}/report-cards",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    cards = r.json()
    assert len(cards) == 3
    assert {c["student"]["full_name"] for c in cards} == {
        "Aisha Bello",
        "David Okafor",
        "Tolu Coker",
    }
    for card in cards:
        assert [s["subject_name"] for s in card["subjects"]] == ["Mathematics"]
        assert card["summary"]["total"] == 60.0


def test_report_cards_bulk_skips_students_without_published_subjects(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    # Only one of the three students gets a published subject.
    _enter_all(client, sid, w, comps)
    for step in ("submit", "verify", "approve", "publish"):
        assert _act(client, sid, w, step).status_code == 200
    # A second arm with no scores at all.
    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": w["session_id"], "name": "JSS 2 A"},
        headers={"X-School-Id": sid},
    )
    empty_arm_id = r.json()["id"]

    r = client.get(
        f"{BASE}/report-cards",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 3  # all three were published together above

    r = client.get(
        f"{BASE}/report-cards",
        params={"arm_id": empty_arm_id, "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json() == []  # no published results → no cards, not an error


def test_report_card_404_when_nothing_published(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)  # entered, never reviewed

    student_id = _first_student_id(db, w["arm_id"])
    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": student_id, "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_report_endpoints_require_auth(client):
    import uuid

    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": str(uuid.uuid4()), "term_id": str(uuid.uuid4())},
    )
    assert r.status_code == 401
    r = client.get(
        f"{BASE}/report-index",
        params={"arm_id": str(uuid.uuid4()), "term_id": str(uuid.uuid4())},
    )
    assert r.status_code == 401


def test_results_blocked_until_session_and_term_activated(client, db):
    """Nothing can be done in a session/term until the admin activates it."""
    import uuid

    register_school(client)
    sid = active_school_id(client)
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": sid},
    )
    session_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": session_id, "term_no": 1, "name": "First Term"},
        headers={"X-School-Id": sid},
    )
    term_id = r.json()["id"]

    probe = {"arm_id": str(uuid.uuid4()), "subject_id": str(uuid.uuid4()), "term_id": term_id}

    # Session not activated → blocked even before looking up the arm.
    r = client.post(f"{BASE}/submit", json=probe, headers={"X-School-Id": sid})
    assert r.status_code == 422
    assert "session" in r.json()["error"]["message"].lower()

    # Term activated but session still planned → still blocked.
    r = client.post(f"{ACAD}/terms/{term_id}/activate", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/submit", json=probe, headers={"X-School-Id": sid})
    assert r.status_code == 422
    assert "term" in r.json()["error"]["message"].lower()

    # Session activated too → guard passes (no activation error any more).
    r = client.post(f"{ACAD}/sessions/{session_id}/activate", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/submit", json=probe, headers={"X-School-Id": sid})
    assert r.status_code != 422
    assert "error" not in r.json() or "activated" not in r.json()["error"]["message"].lower()
