"""School copilot tests: the deterministic, data-grounded Q&A engine.

Pinned behavior:
* Every route is gated on ``ai.copilot`` (401 unauthenticated; 403 for a role
  without it — e.g. secretary).
* Answers are grounded in real rows: overview/snapshot counts match the seeded
  world; performance intents (top performers, subject average, term summary)
  read ONLY published snapshots — a student who was never scored/published is
  never quoted.
* Follow-ups resolve from conversation context ("how many girls?" after naming
  the arm); unknown questions are answered honestly (never fabricated numbers);
  each assistant turn meters exactly one ``AiUsage`` + one monthly ``UsageMeter``
  row under feature ``ai.copilot`` / model ``schoolos-copilot-v1``.
* Conversations are tenant-isolated: school B cannot read school A's thread.
"""
from sqlalchemy import select

from app.models import AiUsage, UsageMeter
from .conftest import active_school_id, enable_premium, register_school
from .test_portal import (
    _act,
    _add_components,
    _add_limited_user,
    _configure,
    _enter_all,
    _publish,
)

COPILOT = "/api/copilot"


def _ask(client, sid, question, *, conversation_id=None, term_id=None, status=201):
    headers = {"X-School-Id": sid} if sid else {}
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if term_id:
        body["term_id"] = term_id
    r = client.post(f"{COPILOT}/ask", json=body, headers=headers)
    assert r.status_code == status, r.text
    return r.json()


def _enter_indices(client, sid, w, comps, indexes, score=60):
    """Score only the listed enrollments (indexes into w['enrollment_ids'])."""
    entries = [
        {
            "student_enrollment_id": w["enrollment_ids"][i],
            "scores": [
                {"assessment_component_id": comps[comp], "score": score}
                for comp in ("CA1", "CA2", "Exam")
            ],
        }
        for i in indexes
    ]
    r = client.put(
        "/api/results/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": entries,
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text


# --- Permission gating ----------------------------------------------------------
def test_ask_requires_ai_copilot(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    _configure(client, sid, db)

    r = client.post(
        f"{COPILOT}/ask", json={"question": "how many students are enrolled?"}
    )
    assert r.status_code == 401

    user = _add_limited_user(db, sid, "secretary")
    client.post("/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"})
    r = client.post(
        f"{COPILOT}/ask",
        json={"question": "how many students are enrolled?"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_intents_endpoint_gated(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    r = client.get(f"{COPILOT}/intents", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    ids = {i["id"] for i in r.json()}
    assert "school_overview" in ids
    assert "top_performers" in ids
    assert "student_report" in ids

    user = _add_limited_user(db, sid, "secretary")
    client.post("/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"})
    r = client.get(f"{COPILOT}/intents", headers={"X-School-Id": sid})
    assert r.status_code == 403


# --- Grounded answers -----------------------------------------------------------
def test_school_overview_counts(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)  # 3 students, 1 arm, 1 level, 1 subject

    msg = _ask(client, sid, "how many students are enrolled?")["message"]
    assert msg["intent"] == "school_overview"
    assert msg["answer_payload"]["students"] == 3
    assert "3" in msg["content"]


def test_class_snapshot_gender(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)  # STU-001/003 male, STU-002 female

    msg = _ask(client, sid, "how many boys are in JSS 1A?")["message"]
    assert msg["intent"] == "class_snapshot"
    assert msg["answer_payload"]["class"] == "JSS 1 A"  # level "JSS 1" + arm "A"
    assert msg["answer_payload"]["boys"] == 2
    assert "2 boys" in msg["content"]

    msg = _ask(client, sid, "how many girls are in JSS 1A?")["message"]
    assert msg["answer_payload"]["girls"] == 1


def test_class_subjects(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    msg = _ask(client, sid, "what subjects does JSS 1A offer?")["message"]
    assert msg["intent"] == "class_subjects"
    assert msg["answer_payload"]["subject_names"] == ["Mathematics"]


# --- Published-only performance intents -----------------------------------------
def test_top_performers_reads_published_only(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_indices(client, sid, w, comps, [0, 1], score=85)  # 2 of 3 scored
    for step in ("submit", "verify", "approve", "publish"):
        assert _act(client, sid, w, step).status_code == 200, step

    msg = _ask(
        client, sid, "who scored highest in Mathematics?", term_id=w["term_id"]
    )["message"]
    assert msg["intent"] == "top_performers"
    payload = msg["answer_payload"]
    assert payload["subject"] == "Mathematics"
    assert len(payload["rows"]) == 2
    names = {row["full_name"] for row in payload["rows"]}
    assert {"Aisha Bello", "David Okafor"} <= names
    assert "Tolu Coker" not in names  # never scored -> never published -> not quoted
    assert all(row["total"] == 85 for row in payload["rows"])
    assert "Mathematics" in msg["content"]


def test_subject_average_published(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)  # all 3 at 60

    msg = _ask(
        client, sid, "what's the average score in Mathematics?", term_id=w["term_id"]
    )["message"]
    assert msg["intent"] == "subject_average"
    p = msg["answer_payload"]
    assert p["subject"] == "Mathematics"
    assert p["published"] == 3
    assert p["average"] == 60.0
    assert "60.00" in msg["content"]


def test_term_summary_requires_scope_then_respects_it(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)

    # No term scoped and no activated (current) term in the world.
    from app.models import Term

    term = db.get(Term, w["term_id"])
    term.is_current = False
    db.flush()
    msg = _ask(client, sid, "how did the class do overall?")["message"]
    assert "No term is set" in msg["content"]

    msg = _ask(
        client, sid, "how did the class do overall?", term_id=w["term_id"]
    )["message"]
    assert msg["intent"] == "term_summary"
    p = msg["answer_payload"]
    assert p["published_cards"] == 3
    assert p["class_average"] == 60.0


# --- Conversation + context ------------------------------------------------------
def test_follow_up_uses_conversation_context(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    conv = None
    for q in ("how many students are in JSS 1A?", "how many girls?"):
        result = _ask(client, sid, q, conversation_id=conv)
        conv = result["conversation"]["id"]

    msg = result["message"]
    assert msg["intent"] == "class_snapshot"
    assert msg["answer_payload"]["class"] == "JSS 1 A"
    assert msg["answer_payload"]["girls"] == 1


def test_conversation_history(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    result = _ask(client, sid, "how many students are enrolled?")
    conv_id = result["conversation"]["id"]
    result = _ask(client, sid, "how many boys are in JSS 1A?", conversation_id=conv_id)

    r = client.get(f"{COPILOT}/conversations", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1

    r = client.get(f"{COPILOT}/conversations/{conv_id}", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["messages"]) == 4  # 2 user + 2 assistant
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"


# --- Honesty + metering ----------------------------------------------------------
def test_unknown_question_is_honest_and_metered(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    msg = _ask(
        client, sid, "what is the meaning of life, the universe and everything?"
    )["message"]
    assert msg["intent"] == "unknown"
    assert "couldn't understand" in msg["content"]
    # The decline is static help copy (its examples may incidentally use names
    # like the seeded students' — that is not a data read). What it must never
    # do is surface *rows* from this school: no admission numbers and no score
    # figures, which only a real query could produce.
    for leak in ("STU-", "60", "85"):
        assert leak not in msg["content"]


def test_metering_one_per_assistant_turn(client, db):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    conv = None
    for q in ("help", "how many students are enrolled?"):
        result = _ask(client, sid, q, conversation_id=conv)
        conv = result["conversation"]["id"]

    usages = db.scalars(
        select(AiUsage).where(AiUsage.feature == "ai.copilot")
    ).all()
    assert len(usages) == 2
    assert {u.model for u in usages} == {"schoolos-copilot-v1"}  # noqa: C405

    meters = db.scalars(
        select(UsageMeter).where(UsageMeter.feature_code == "ai.copilot")
    ).all()
    assert len(meters) == 1
    assert meters[0].count == 2


# --- Tenancy isolation -----------------------------------------------------------
def test_conversation_is_tenant_isolated(client, db):
    register_school(client, name="School A", email="a@school.edu")
    sid_a = active_school_id(client)
    enable_premium(db, sid_a)
    w_a = _configure(client, sid_a, db)
    conv_id = _ask(client, sid_a, "how many students are enrolled?")["conversation"][
        "id"
    ]

    register_school(client, name="School B", email="b@school.edu")
    sid_b = active_school_id(client)
    enable_premium(db, sid_b)
    r = client.get(
        f"{COPILOT}/conversations/{conv_id}", headers={"X-School-Id": sid_b}
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"