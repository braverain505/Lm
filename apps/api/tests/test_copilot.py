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
  row under feature ``ai.copilot`` / model ``clearis-copilot-v1``.
* Conversations are tenant-isolated: school B cannot read school A's thread.
"""
import uuid

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


def test_greeting_is_small_talk_not_a_data_dump(client, db):
    """"how are you doing?" contains the word "how" — it must not be answered
    as a school-overview query."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    _configure(client, sid, db)

    for question in ("hello", "how are you doing?", "thanks!"):
        msg = _ask(client, sid, question)["message"]
        assert msg["intent"] == "small_talk", question
        # The reply is a greeting, not the school's statistics: no count cards.
        assert "students" not in msg["answer_payload"]
        assert "teachers" not in msg["answer_payload"]
        assert "enrolled students" not in msg["content"]

    # A personal "how am I doing" is honestly out of scope, not a stats dump.
    msg = _ask(client, sid, "how am I doing?")["message"]
    assert msg["intent"] == "small_talk"
    assert "records" in msg["content"]

    # But a greeting wrapped around a real question still routes to the catalog.
    msg = _ask(client, sid, "hi, how many students are enrolled?")["message"]
    assert msg["intent"] == "school_overview"
    assert msg["answer_payload"]["students"] == 3


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
    assert {u.model for u in usages} == {"clearis-copilot-v1"}  # noqa: C405

    meters = db.scalars(
        select(UsageMeter).where(UsageMeter.feature_code == "ai.copilot")
    ).all()
    assert len(meters) == 1
    assert meters[0].count == 2


# --- Tenancy isolation -----------------------------------------------------------
# --- The LLM layer ---------------------------------------------------------
#
# The suite runs with no Groq key (see conftest), so every test above pins the
# documented offline behaviour: the rules answer, `source="rules"`, metered as
# the local model. These tests turn a *fake* provider on to pin the other half —
# that the model is handed the school's real numbers, that its prose is used and
# billed as the real provider's, and that every failure mode falls back instead
# of failing the turn.


def _fake_llm(text="The school has 3 enrolled students this term."):
    """A stand-in for ``llm_client.complete_text`` that records what it was sent."""
    from app.services.llm_client import LlmResult

    calls: list[dict] = []

    def _complete(*, system, user, temperature=0.3, max_tokens=2400):
        calls.append({"system": system, "user": user})
        if text is None:
            return None
        return LlmResult(
            text=text,
            model="openai/gpt-oss-120b",
            tokens_in=1234,
            tokens_out=56,
            latency_ms=42,
        )

    return _complete, calls


def _enable_llm(monkeypatch):
    """Turn the provider on for one test, without touching the real key."""
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "test-key", raising=False)


def test_llm_answer_is_used_and_metered_as_the_real_provider(client, db, monkeypatch):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)

    _enable_llm(monkeypatch)
    fake, calls = _fake_llm("Three students are enrolled in this school right now.")
    monkeypatch.setattr("app.services.copilot_service.complete_text", fake)

    msg = _ask(client, sid, "how many students are enrolled?")["message"]

    # The model's prose is what the user reads...
    assert msg["content"] == "Three students are enrolled in this school right now."
    assert msg["answer_payload"]["source"] == "llm"
    assert msg["answer_payload"]["model"] == "openai/gpt-oss-120b"
    # ...the resolved facts still travel with it, so the UI cards keep working.
    assert msg["answer_payload"]["students"] == 3
    assert msg["intent"] == "school_overview"

    # Metered once, against the real provider and its real token counts.
    usage = db.scalars(select(AiUsage).where(AiUsage.feature == "ai.copilot")).all()
    assert len(usage) == 1
    assert usage[0].provider == "groq"
    assert usage[0].model == "openai/gpt-oss-120b"
    assert usage[0].tokens_in == 1234
    assert usage[0].tokens_out == 56

    # And the prompt really was grounded on this school's own rows.
    sent = calls[0]["user"]
    assert "3 enrolled students" in sent
    assert "JSS 1 A (3 students)" in sent
    assert "Mathematics" in sent


def test_grounding_brief_carries_real_facts_not_inventions(client, db):
    """Every number the model may state comes from the school's own rows."""
    from app.services.copilot_service import _grounding_brief
    from app.services.results_service import report_card  # noqa: F401 - import check

    register_school(client, name="Brightfield Academy")
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _publish(client, sid, w, comps)

    from app.models import Term

    term = db.get(Term, w["term_id"])
    # The service is handed the tenant UUID (never the header's string form).
    brief = _grounding_brief(
        db,
        uuid.UUID(sid),
        term=term,
        deterministic_text="There are 3 enrolled students.",
        deterministic_payload={"intent": "school_overview", "students": 3},
    )

    assert "Brightfield Academy" in brief
    assert "3 enrolled students" in brief
    assert "JSS 1 A (3 students)" in brief
    assert "Mathematics" in brief
    assert "First Term" in brief            # the term in scope
    assert "students entered" in brief      # live score-entry progress
    assert '"students": 3' in brief         # the rules engine's resolved facts
    assert "only facts you may use" in brief.lower() or "authoritative" in brief


def test_llm_unusable_output_falls_back_to_rules(client, db, monkeypatch):
    """A refusal, a stub or a rambling answer must not become the card's answer."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    _configure(client, sid, db)

    _enable_llm(monkeypatch)
    for unusable in (None, "ok", "x" * 5000):
        fake, _ = _fake_llm(unusable)
        monkeypatch.setattr("app.services.copilot_service.complete_text", fake)
        msg = _ask(client, sid, "how many students are enrolled?")["message"]
        assert msg["answer_payload"]["source"] == "rules"
        assert "3" in msg["content"]
        # ...and the fallback is billed locally, not as a Groq response.
    usages = db.scalars(select(AiUsage).where(AiUsage.feature == "ai.copilot")).all()
    assert {u.provider for u in usages} == {"local"}
    assert {u.model for u in usages} == {"clearis-copilot-v1"}


def test_provider_exception_never_fails_the_turn(client, db, monkeypatch):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    _configure(client, sid, db)

    _enable_llm(monkeypatch)

    def _boom(**_):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr("app.services.copilot_service.complete_text", _boom)
    msg = _ask(client, sid, "how many students are enrolled?")["message"]
    assert msg["answer_payload"]["source"] == "rules"
    assert "3" in msg["content"]


def test_llm_can_answer_a_question_no_intent_matches(client, db, monkeypatch):
    """The catalog is not the limit any more — grounded questions outside it get
    a real answer, and unmatched ones are still labelled honestly."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    _configure(client, sid, db)

    _enable_llm(monkeypatch)
    fake, calls = _fake_llm("This school has one subject on record, Mathematics.")
    monkeypatch.setattr("app.services.copilot_service.complete_text", fake)

    msg = _ask(client, sid, "tell me about the school's offering")["message"]
    assert msg["answer_payload"]["source"] == "llm"
    assert msg["content"].startswith("This school has one subject")
    # The rules engine could not classify it — the payload says so rather than
    # claiming a match, and the school's subjects were still in the brief.
    assert "Mathematics" in calls[0]["user"]


def test_follow_up_history_is_sent_to_the_model(client, db, monkeypatch):
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    _configure(client, sid, db)

    _enable_llm(monkeypatch)
    fake, calls = _fake_llm("There are 2 boys in that class.")
    monkeypatch.setattr("app.services.copilot_service.complete_text", fake)

    conv = None
    for q in ("how many students are in JSS 1A?", "how many girls?"):
        result = _ask(client, sid, q, conversation_id=conv)
        conv = result["conversation"]["id"]

    # The second prompt carries the first turn, and the current question exactly
    # once (not duplicated by the pending-turn bookkeeping).
    second = calls[1]["user"]
    assert "how many students are in JSS 1A?" in second
    assert second.count("Current question: how many girls?") == 1


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