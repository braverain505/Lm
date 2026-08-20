"""AI question-bank tests: generation is gated on ``results.comment``, composes
a deterministic practice set grounded in the school's own subject/class/term/
topic, stores ONE ``QuestionBank`` row per cell (``revision`` bumps on
regeneration), and meters every generation into ``ai_usage`` + the monthly
``usage_meters`` rollup under feature ``ai.question.bank``.

Like the comment and lesson-plan engines, this one is local & deterministic —
tests pin the *content*: every item's correct answer must follow the subject's
strand (math banks calculate/solve, humanities banks explain/discuss), and no
strand's correct answer may borrow another strand's wording.
"""
from sqlalchemy import select

from app.models import AiUsage, QuestionBank, UsageMeter
from .conftest import active_school_id, enable_premium, register_school
from .test_portal import _add_limited_user, _configure

BANKS = "/api/question-banks"


def _bank_url(w, topic="Linear Equations"):
    return (
        f"{BANKS}?term_id={w['term_id']}&subject_id={w['subject_id']}"
        f"&class_arm_id={w['arm_id']}&topic={topic}"
    )


def _bank_payload(w, topic="Linear Equations", count=5) -> dict:
    return {
        "term_id": w["term_id"],
        "subject_id": w["subject_id"],
        "class_arm_id": w["arm_id"],
        "topic": topic,
        "count": count,
    }


def _correct_options(bank: dict) -> list[str]:
    return [q["options"][q["answer"]] for q in bank["questions"]]


# --- Permission gating ----------------------------------------------------------
def test_generate_requires_results_comment(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(BANKS, json=_bank_payload(w))
    assert r.status_code == 401

    user = _add_limited_user(db, sid, "secretary")
    client.post("/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"})
    r = client.post(BANKS, json=_bank_payload(w), headers={"X-School-Id": sid})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_get_requires_results_view(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(BANKS, json=_bank_payload(w), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    r = client.get(_bank_url(w), headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text

    r = client.get(_bank_url(w))
    assert r.status_code == 401


def test_generate_writes_bank_and_metering(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(BANKS, json=_bank_payload(w), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["term_id"] == w["term_id"]
    assert body["subject_id"] == w["subject_id"]
    assert body["class_arm_id"] == w["arm_id"]
    assert body["topic"] == "Linear Equations"
    assert body["provider"] == "local"
    assert body["model"] == "schoolos-question-v1"
    assert body["revision"] == 1
    assert body["generated_at"]

    # The bank is data-grounded: real subject/class/term/topic all appear.
    bank = body["bank"]
    assert "Linear Equations" in bank["title"]
    assert bank["subject"] == "Mathematics"
    assert bank["class_level"] == "JSS 1 A"
    assert bank["term"] == "First Term"
    assert bank["count"] == 5
    assert len(bank["questions"]) == 5
    for q in bank["questions"]:
        assert q["type"] == "multiple_choice"
        assert q["stem"]
        assert len(q["options"]) == 4
        assert q["answer"] in range(4)
        assert q["rationale"]

    # Metering: one AiUsage row + one monthly UsageMeter bump.
    usage = db.scalars(select(AiUsage)).all()
    assert len(usage) == 1
    assert usage[0].feature == "ai.question.bank"
    assert usage[0].provider == "local"
    assert usage[0].model == "schoolos-question-v1"
    assert usage[0].tokens_in >= 1
    meter = db.scalars(select(UsageMeter)).all()
    assert len(meter) == 1
    assert meter[0].feature_code == "ai.question.bank"
    assert meter[0].count == 1

    # Stored bank row exists & is fetchable.
    rows = db.scalars(select(QuestionBank)).all()
    assert len(rows) == 1
    r = client.get(_bank_url(w), headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["bank"]["title"] == bank["title"]


def test_bank_correct_answers_follow_subject_strand(client, db):
    """Mathematics must render through the maths strand — 'calculate'/'solve'
    correct answers; a humanities subject ('Civic Education') must use its own
    strand and never mark a calculating answer correct."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(BANKS, json=_bank_payload(w, topic="Linear Equations"),
                    headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    math_correct = _correct_options(r.json()["bank"])
    assert any("calculate" in o for o in math_correct)
    assert any("solve" in o for o in math_correct)

    r = client.post(
        "/api/academics/subjects",
        json={"name": "Civic Education", "code": "CVE"},
        headers={"X-School-Id": sid},
    )
    civic_id = r.json()["id"]
    payload = _bank_payload(w, topic="Citizenship")
    payload["subject_id"] = civic_id
    r = client.post(BANKS, json=payload, headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    civic_correct = _correct_options(r.json()["bank"])
    assert any("explain" in o or "discuss" in o for o in civic_correct)
    assert not any("calculate" in o for o in civic_correct)


def test_regenerate_bumps_revision_and_meters_again(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r1 = client.post(BANKS, json=_bank_payload(w), headers={"X-School-Id": sid})
    assert r1.status_code == 201
    assert r1.json()["revision"] == 1

    r2 = client.post(BANKS, json=_bank_payload(w), headers={"X-School-Id": sid})
    assert r2.status_code == 201
    assert r2.json()["revision"] == 2
    assert r2.json()["bank"] == r1.json()["bank"]  # same inputs → same bank

    # Still exactly one bank row; two AI rows; two meter bumps.
    assert len(db.scalars(select(QuestionBank)).all()) == 1
    assert len(db.scalars(select(AiUsage)).all()) == 2
    meter = db.scalars(select(UsageMeter)).all()
    assert len(meter) == 1
    assert meter[0].count == 2


def test_generate_respects_count(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.post(BANKS, json=_bank_payload(w, count=3), headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    assert r.json()["bank"]["count"] == 3
    assert len(r.json()["bank"]["questions"]) == 3


def test_generate_404_for_unknown_subject(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    payload = _bank_payload(w)
    payload["subject_id"] = "00000000-0000-0000-0000-000000000000"

    r = client.post(BANKS, json=payload, headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_get_missing_bank_404(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    r = client.get(_bank_url(w, topic="Unseen Topic"), headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"