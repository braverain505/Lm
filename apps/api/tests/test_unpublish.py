"""Unpublishing results — a platform-administrator action, and only that.

A published term is the document parents hold, so a school cannot take it back on
its own. When the structure itself is wrong (an office published before the
scoresheet was right), a Clearis platform admin can return the term's results to
draft — archiving the published cards first — so the school can correct the
scoresheet and re-publish through the normal pipeline.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models import AuditLog, Term, User
from app.models.results import Result, ResultEvent, Score, TermResultArchive

from .conftest import active_school_id, register_school
from .test_results import _act, _add_components, _configure, _enter_all

BASE = "/api/results"
PLATFORM = "/api/platform"


def _published_term(client, db) -> dict:
    """A school with one subject fully published for the term."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)
    assert _act(client, sid, w, "submit").status_code == 200
    assert _act(client, sid, w, "verify").status_code == 200
    assert _act(client, sid, w, "approve").status_code == 200
    assert _act(client, sid, w, "publish").status_code == 200
    return {"sid": sid, **w}


def _make_platform_admin(db) -> None:
    user = db.scalar(select(User).where(User.email == "admin@test.edu"))
    user.is_superadmin = True
    db.commit()


def test_a_school_cannot_unpublish_its_own_results(client, db):
    world = _published_term(client, db)
    response = client.post(
        f"{PLATFORM}/schools/{world['sid']}/results/unpublish",
        json={"term_id": world["term_id"], "reason": "The scoresheet was wrong."},
    )
    assert response.status_code == 403
    # And nothing moved.
    published = db.scalar(
        select(func.count()).select_from(Result).where(Result.status == "published")
    )
    assert published == len(world["enrollment_ids"])


def test_a_platform_admin_unpublishes_archives_and_journals(client, db):
    world = _published_term(client, db)
    _make_platform_admin(db)

    summary = client.get(f"{PLATFORM}/schools/{world['sid']}/results")
    assert summary.status_code == 200, summary.text
    term_row = next(row for row in summary.json() if row["term_id"] == world["term_id"])
    assert term_row["published"] == len(world["enrollment_ids"])

    scores_before = db.scalar(select(func.count()).select_from(Score))

    response = client.post(
        f"{PLATFORM}/schools/{world['sid']}/results/unpublish",
        json={
            "term_id": world["term_id"],
            "reason": "The exam office published before the nursery scoresheet was corrected.",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unpublished"] == len(world["enrollment_ids"])
    assert body["archive_version"] == 1

    # Results are back to draft, with no publish stamps left behind.
    rows = list(
        db.scalars(select(Result).where(Result.term_id == uuid.UUID(world["term_id"])))
    )
    assert rows and all(row.status == "draft" for row in rows)
    assert all(row.published_snapshot is None for row in rows)
    assert all(row.published_at is None for row in rows)

    # The published cards were archived first, so the version parents saw is kept.
    archive = db.scalar(
        select(TermResultArchive).where(
            TermResultArchive.term_id == uuid.UUID(world["term_id"])
        )
    )
    assert archive is not None and archive.version == 1

    # The marks themselves were not touched.
    assert db.scalar(select(func.count()).select_from(Score)) == scores_before

    # Every row and the platform audit trail record who did it and why.
    events = list(
        db.scalars(select(ResultEvent).where(ResultEvent.action == "unpublish"))
    )
    assert len(events) == len(world["enrollment_ids"])
    assert all("scoresheet" in (event.note or "") for event in events)
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "unpublish"))
    assert audit is not None and "scoresheet" in (audit.details or "")


def test_unpublishing_lifts_the_scoresheet_lock_for_that_term(client, db):
    world = _published_term(client, db)
    _make_platform_admin(db)

    before = client.get(
        f"{BASE}/scoresheet", headers={"X-School-Id": world["sid"]}
    ).json()
    assert before["locked"] is True

    response = client.post(
        f"{PLATFORM}/schools/{world['sid']}/results/unpublish",
        json={"term_id": world["term_id"], "reason": "Correcting the assessment structure."},
    )
    assert response.status_code == 200, response.text

    after = client.get(
        f"{BASE}/scoresheet", headers={"X-School-Id": world["sid"]}
    ).json()
    assert after["locked"] is False
    # With the lock lifted, the structure can be saved into the current term.
    saved = client.put(
        f"{BASE}/scoresheet",
        json={
            "mode": "same",
            "default": [
                {"name": "1st CA", "max_score": 15},
                {"name": "2nd CA", "max_score": 15},
                {"name": "Exam", "max_score": 70},
            ],
            "sections": {},
        },
        headers={"X-School-Id": world["sid"]},
    )
    assert saved.status_code == 200, saved.text
    assert [row["max_score"] for row in saved.json()["default"]] == [15.0, 15.0, 70.0]


def test_unpublishing_twice_is_a_no_op(client, db):
    world = _published_term(client, db)
    _make_platform_admin(db)
    first = client.post(
        f"{PLATFORM}/schools/{world['sid']}/results/unpublish",
        json={"term_id": world["term_id"], "reason": "First correction."},
    )
    assert first.status_code == 200 and first.json()["unpublished"] > 0

    second = client.post(
        f"{PLATFORM}/schools/{world['sid']}/results/unpublish",
        json={"term_id": world["term_id"], "reason": "Second attempt."},
    )
    assert second.status_code == 200
    assert second.json()["unpublished"] == 0
    # No second archive is written for a term with nothing published.
    assert second.json()["archive_version"] is None