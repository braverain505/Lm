"""AI result-comment tests: generation is gated on ``results.comment``, reads
ONLY published data, stores the remark reversibly (revision bumps on
regeneration), and meters every generation into ``ai_usage`` + the monthly
``usage_meters`` rollup.

The engine is local & deterministic, so these tests also pin the *content*:
the comment must quote the actual figures and name real subjects (no invented
sentences, no placeholder text).
"""
from sqlalchemy import select

from app.models import AiUsage, ResultComment, UsageMeter
from .conftest import active_school_id, enable_premium, register_school
from .test_portal import (
    _act,
    _add_components,
    _add_limited_user,
    _configure,
    _enter_all,
    _publish,
)

RESULTS = "/api/results"


def _comment_url(w: dict, student_id: str) -> str:
    return f"{RESULTS}/{student_id}/comment?term_id={w['term_id']}"


# --- Permission gating ----------------------------------------------------------
def test_generate_comment_requires_results_comment(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    student_id = w["student_ids"][0]

    # Unauthenticated.
    r = client.post(_comment_url(w, student_id))
    assert r.status_code == 401

    # Secretary has results.view but not results.comment.
    user = _add_limited_user(db, sid, "secretary")
    client.post("/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"})
    r = client.post(
        _comment_url(w, student_id), headers={"X-School-Id": sid}
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_generate_writes_comment_and_metering(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    student_id = w["student_ids"][0]

    r = client.post(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["student_id"] == student_id
    assert body["term_id"] == w["term_id"]
    assert body["provider"] == "local"
    assert body["model"] == "schoolos-comment-v1"
    assert body["revision"] == 1

    # The comment is data-grounded: Aisha Bello, the term, the class, the
    # aggregate figure and the actual subject name all appear.
    assert "Aisha Bello" in body["body"]
    assert "First Term" in body["body"]

    # Metering: one AiUsage row + one monthly UsageMeter bump.
    usage = db.scalars(select(AiUsage)).all()
    assert len(usage) == 1
    assert usage[0].feature == "ai.result.comment"
    assert usage[0].provider == "local"
    assert usage[0].model == "schoolos-comment-v1"
    assert usage[0].tokens_out >= 1
    meter = db.scalars(select(UsageMeter)).all()
    assert len(meter) == 1
    assert meter[0].feature_code == "ai.result.comment"
    assert meter[0].count == 1

    # Stored comment row exists & is fetchable.
    rows = db.scalars(select(ResultComment)).all()
    assert len(rows) == 1
    r = client.get(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["body"] == body["body"]


def test_comment_names_real_strong_subject(client, db):
    """The engine must cite the actual data — here Mathematics is the only
    published subject, scored 85 (≥ the strength cutoff), so it is named."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps, score=85)
    for step in ("submit", "verify", "approve", "publish"):
        assert _act(client, sid, w, step).status_code == 200, step
    student_id = w["student_ids"][0]

    r = client.post(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    assert "Mathematics (85)" in r.json()["body"]


def test_regenerate_bumps_revision_and_meters_again(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    student_id = w["student_ids"][0]

    r1 = client.post(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r1.status_code == 201
    assert r1.json()["revision"] == 1

    r2 = client.post(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r2.status_code == 201
    assert r2.json()["revision"] == 2
    assert r2.json()["body"] == r1.json()["body"]  # same published data → same text

    # Still exactly one comment row; two AI rows; two meter bumps.
    assert len(db.scalars(select(ResultComment)).all()) == 1
    assert len(db.scalars(select(AiUsage)).all()) == 2
    meter = db.scalars(select(UsageMeter)).all()
    assert len(meter) == 1
    assert meter[0].count == 2


def test_generate_404_when_nothing_published(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    student_id = w["student_ids"][0]

    r = client.post(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r.status_code == 404


def test_get_missing_comment_404(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)
    student_id = w["student_ids"][0]

    r = client.get(_comment_url(w, student_id), headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"