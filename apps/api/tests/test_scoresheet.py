"""The school's configurable scoresheet.

A school defines its assessment structure once in settings — the components and
what each is marked out of — and it stays in force until the school changes it.
These tests cover: the built-in default before anything is saved, the derived
shares, carrying into a new term, validation, renaming a row without losing its
scores, and the published-term guard.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models import AssessmentComponent, Result, Score
from .conftest import active_school_id, register_school
from .test_results import _configure

BASE = "/api/results"
ACAD = "/api/academics"


def _put(client, school_id, rows, *, mode="same", sections=None):
    return client.put(
        f"{BASE}/scoresheet",
        json={"mode": mode, "default": rows, "sections": sections or {}},
        headers={"X-School-Id": school_id},
    )


def _components(client, school_id, term_id):
    r = client.get(
        f"{BASE}/components?term_id={term_id}",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_default_scoresheet_before_the_school_saves_one(client, db):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    r = client.get(f"{BASE}/scoresheet", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_custom"] is False
    assert [c["name"] for c in body["default"]] == ["1st CA", "2nd CA", "Exam"]
    assert body["marks_total"] == 120.0
    assert body["applied_term_name"] == "First Term"
    assert body["locked"] is False


def test_saving_a_scoresheet_derives_proportional_shares(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    r = _put(client, sid, [
        {"name": "1st CA", "max_score": 10},
        {"name": "2nd CA", "max_score": 10},
        {"name": "3rd CA", "max_score": 10},
        {"name": "Exam", "max_score": 100},
    ])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_custom"] is True
    assert body["marks_total"] == 130.0
    # The exam is 100 of 130 marks, so it carries 76.93 of the final 100; the
    # rounding residue lands on the largest component so the set totals exactly.
    assert [c["weight"] for c in body["default"]] == [7.69, 7.69, 7.69, 76.93]

    # In force for the current term immediately.
    comps = _components(client, sid, cfg["term_id"])
    assert [(c["name"], c["max_score"], c["weight"]) for c in comps] == [
        ("1st CA", 10.0, 7.69),
        ("2nd CA", 10.0, 7.69),
        ("3rd CA", 10.0, 7.69),
        ("Exam", 100.0, 76.93),
    ]


def test_scoresheet_carries_into_a_new_term(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    r = _put(client, sid, [
        {"name": "1st CA", "max_score": 20},
        {"name": "2nd CA", "max_score": 20},
        {"name": "Exam", "max_score": 60},
    ])
    assert r.status_code == 200, r.text

    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": cfg["session_id"], "term_no": 2, "name": "Second Term"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    term2 = r.json()["id"]
    r = client.post(f"{ACAD}/terms/{term2}/activate", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text

    # A brand-new term is seeded from the school's scoresheet, not the old trio.
    comps = _components(client, sid, term2)
    assert [(c["name"], c["max_score"]) for c in comps] == [
        ("1st CA", 20.0), ("2nd CA", 20.0), ("Exam", 60.0),
    ]
    assert round(sum(c["weight"] for c in comps), 2) == 100.0


@pytest.mark.parametrize(
    "components",
    [
        [],
        [{"name": "", "max_score": 20}],
        [{"name": "CA", "max_score": 10}, {"name": "ca", "max_score": 10}],
        [{"name": "CA", "max_score": 0}],
        [{"name": "CA", "max_score": -5}],
    ],
)
def test_an_invalid_scoresheet_is_rejected(client, db, components):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    r = _put(client, sid, components)
    assert r.status_code == 422, r.text


def test_renaming_a_row_keeps_its_component_and_scores(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    r = _put(client, sid, [
        {"name": "1st CA", "max_score": 20},
        {"name": "Exam", "max_score": 80},
    ])
    assert r.status_code == 200, r.text
    first_key = r.json()["default"][0]["key"]
    ca = _components(client, sid, cfg["term_id"])[0]

    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": cfg["arm_id"],
            "subject_id": cfg["subject_id"],
            "term_id": cfg["term_id"],
            "entries": [{
                "student_enrollment_id": cfg["enrollment_ids"][0],
                "scores": [{"assessment_component_id": ca["id"], "score": 15}],
            }],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    # Rename the row, echoing its key back as the editor does.
    r = _put(client, sid, [
        {"key": first_key, "name": "First CA", "max_score": 20},
        {"name": "Exam", "max_score": 80},
    ])
    assert r.status_code == 200, r.text

    comps = _components(client, sid, cfg["term_id"])
    assert comps[0]["name"] == "First CA"
    assert str(comps[0]["id"]) == str(ca["id"]), "rename must update the component in place"

    db.expire_all()
    score = db.scalar(
        select(Score).where(Score.assessment_component_id == uuid.UUID(ca["id"]))
    )
    assert score is not None and float(score.score) == 15.0


def test_a_published_term_is_not_restructured(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    r = _put(client, sid, [
        {"name": "1st CA", "max_score": 20},
        {"name": "Exam", "max_score": 80},
    ])
    assert r.status_code == 200, r.text
    before = _components(client, sid, cfg["term_id"])

    # A result in this term is already out.
    db.add(Result(
        school_id=uuid.UUID(sid),
        student_enrollment_id=uuid.UUID(cfg["enrollment_ids"][0]),
        subject_id=uuid.UUID(cfg["subject_id"]),
        term_id=uuid.UUID(cfg["term_id"]),
        class_arm_id=uuid.UUID(cfg["arm_id"]),
        status="published",
    ))
    db.flush()

    r = _put(client, sid, [
        {"name": "1st CA", "max_score": 10},
        {"name": "2nd CA", "max_score": 10},
        {"name": "Exam", "max_score": 80},
    ])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["locked"] is True
    # Stored for future terms...
    assert [c["name"] for c in body["default"]] == ["1st CA", "2nd CA", "Exam"]
    # ...but this term's components are untouched.
    after = _components(client, sid, cfg["term_id"])
    assert [(c["name"], c["id"]) for c in after] == [(c["name"], c["id"]) for c in before]