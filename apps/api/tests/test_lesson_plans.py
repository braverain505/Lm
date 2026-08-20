"""AI lesson-plan tests: generation is gated on ``results.comment``, composes a
deterministic plan grounded in the school's own subject/class/term/topic,
stores ONE ``LessonPlan`` row per cell (``revision`` bumps on regeneration), and
meters every generation into ``ai_usage`` + the monthly ``usage_meters`` rollup
under feature ``ai.lesson.plan``.

Like the comment engine, this one is local & deterministic — tests pin the
*content*: the plan must quote the real subject, class, term and topic, and the
wording must come from the subject's strand (no invented or generic filler).
"""
from sqlalchemy import select

from app.models import AiUsage, LessonPlan, UsageMeter
from .conftest import active_school_id, enable_premium, register_school
from .test_portal import _add_limited_user, _configure

PLANS = "/api/lesson-plans"


def _plan_url(w, topic="Linear Equations"):
    return (
        f"{PLANS}?term_id={w['term_id']}&subject_id={w['subject_id']}"
        f"&class_arm_id={w['arm_id']}&topic={topic}"
    )


def _plan_payload(w, topic="Linear Equations", periods=2) -> dict:
    return {
        "term_id": w["term_id"],
        "subject_id": w["subject_id"],
        "class_arm_id": w["arm_id"],
        "topic": topic,
        "periods": periods,
    }


# --- Permission gating ----------------------------------------------------------
def test_generate_requires_results_comment(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    # Unauthenticated.
    r = client.post(PLANS, json=_plan_payload(w))
    assert r.status_code == 401

    # Secretary has results.view but not results.comment.
    user = _add_limited_user(db, sid, "secretary")
    client.post("/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"})
    r = client.post(PLANS, json=_plan_payload(w), headers={"X-School-Id": sid})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_get_requires_results_view(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(PLANS, json=_plan_payload(w), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    r = client.get(_plan_url(w), headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text

    # Unauthenticated read is rejected.
    r = client.get(_plan_url(w))
    assert r.status_code == 401


def test_generate_writes_plan_and_metering(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(PLANS, json=_plan_payload(w), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["term_id"] == w["term_id"]
    assert body["subject_id"] == w["subject_id"]
    assert body["class_arm_id"] == w["arm_id"]
    assert body["topic"] == "Linear Equations"
    assert body["provider"] == "local"
    assert body["model"] == "schoolos-lesson-v1"
    assert body["revision"] == 1
    assert body["generated_at"]

    # The plan is data-grounded: real subject/class/term/topic all appear.
    plan = body["plan"]
    assert "Linear Equations" in plan["title"]
    assert "Mathematics" in plan["subject"]
    assert "JSS 1 A" in plan["class_level"]
    assert "First Term" in plan["term"]
    assert plan["periods"] == 2
    assert plan["duration_minutes"] == 80
    assert [s["phase"] for s in plan["procedure"]] == [
        "Introduction", "Development", "Evaluation", "Conclusion",
    ]
    assert len(plan["objectives"]) == 3

    # Metering: one AiUsage row + one monthly UsageMeter bump.
    usage = db.scalars(select(AiUsage)).all()
    assert len(usage) == 1
    assert usage[0].feature == "ai.lesson.plan"
    assert usage[0].provider == "local"
    assert usage[0].model == "schoolos-lesson-v1"
    assert usage[0].tokens_in >= 1
    meter = db.scalars(select(UsageMeter)).all()
    assert len(meter) == 1
    assert meter[0].feature_code == "ai.lesson.plan"
    assert meter[0].count == 1

    # Stored plan row exists & is fetchable.
    rows = db.scalars(select(LessonPlan)).all()
    assert len(rows) == 1
    r = client.get(_plan_url(w), headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["plan"]["title"] == plan["title"]


def test_plan_wording_follows_subject_strand(client, db):
    """Mathematics must render through the maths strand — 'calculate'/'solve'
    wording, not the generic humanities vocabulary. A second, humanities
    subject ('Civic Education') must use its own strand instead."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(PLANS, json=_plan_payload(w, topic="Linear Equations"),
                    headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    math_objectives = r.json()["plan"]["objectives"]
    assert any("calculate" in o for o in math_objectives)
    assert any("solve" in o for o in math_objectives)

    # Add a humanities subject and generate for it.
    r = client.post(
        "/api/academics/subjects",
        json={"name": "Civic Education", "code": "CVE"},
        headers={"X-School-Id": sid},
    )
    civic_id = r.json()["id"]
    payload = _plan_payload(w, topic="Citizenship")
    payload["subject_id"] = civic_id
    r = client.post(PLANS, json=payload, headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    civic_objectives = r.json()["plan"]["objectives"]
    assert any("explain" in o for o in civic_objectives)
    assert not any("calculate" in o for o in civic_objectives)


def test_regenerate_bumps_revision_and_meters_again(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r1 = client.post(PLANS, json=_plan_payload(w), headers={"X-School-Id": sid})
    assert r1.status_code == 201
    assert r1.json()["revision"] == 1

    r2 = client.post(PLANS, json=_plan_payload(w), headers={"X-School-Id": sid})
    assert r2.status_code == 201
    assert r2.json()["revision"] == 2
    assert r2.json()["plan"] == r1.json()["plan"]  # same inputs → same plan

    # Still exactly one plan row; two AI rows; two meter bumps.
    assert len(db.scalars(select(LessonPlan)).all()) == 1
    assert len(db.scalars(select(AiUsage)).all()) == 2
    meter = db.scalars(select(UsageMeter)).all()
    assert len(meter) == 1
    assert meter[0].count == 2


def test_generate_404_for_unknown_subject(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    payload = _plan_payload(w)
    payload["subject_id"] = "00000000-0000-0000-0000-000000000000"

    r = client.post(PLANS, json=payload, headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_get_missing_plan_404(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.get(_plan_url(w, topic="Unseen Topic"), headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"