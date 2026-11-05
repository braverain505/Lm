"""Class groups: one position list over classes that are taught separately.

A school that streams a year group (SS 1 Science / Arts / Commercial) still
wants a single standing for the whole year group, computed over the subjects
each pupil actually offers. A class with no ``group_name`` must keep behaving
exactly as it did before class groups existed, so every test here pairs the
grouped arms with an ungrouped control arm.
"""
from sqlalchemy import select

from app.models import ClassArm, Result, StudentEnrollment
from app.seed import seed_grade_scale
from .conftest import active_school_id, grant_permission, register_school
from .test_results import ACAD, BASE, _add_components

GROUP = "SS 1"


def _post(client, sid, path, payload, expect=201):
    r = client.post(path, json=payload, headers={"X-School-Id": sid})
    assert r.status_code == expect, r.text
    return r.json()


def _configure_group(client, sid: str, db) -> dict:
    """Session, term, two grouped arms and one ungrouped control arm.

    Science offers Mathematics and Physics; Arts offers Mathematics only. That
    asymmetry is the point: the two classes sit different numbers of subjects,
    which is why the group standing is ranked on the average.
    """
    session_id = _post(
        client, sid, f"{ACAD}/sessions", {"name": "2025/2026", "is_current": True}
    )["id"]
    term_id = _post(
        client,
        sid,
        f"{ACAD}/terms",
        {"session_id": session_id, "term_no": 1, "name": "First Term"},
    )["id"]
    assert (
        client.post(
            f"{ACAD}/sessions/{session_id}/activate", headers={"X-School-Id": sid}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{ACAD}/terms/{term_id}/activate", headers={"X-School-Id": sid}
        ).status_code
        == 200
    )

    science = _post(
        client,
        sid,
        f"{ACAD}/arms",
        {"session_id": session_id, "name": "SS 1 Science", "group_name": GROUP},
    )
    arts = _post(
        client,
        sid,
        f"{ACAD}/arms",
        {"session_id": session_id, "name": "SS 1 Arts", "group_name": GROUP},
    )
    # The control: a class nobody grouped. Its positions must stay its own.
    solo = _post(
        client, sid, f"{ACAD}/arms", {"session_id": session_id, "name": "SS 3"}
    )

    maths = _post(
        client, sid, f"{ACAD}/subjects", {"name": "Mathematics", "code": "MTH"}
    )
    physics = _post(client, sid, f"{ACAD}/subjects", {"name": "Physics", "code": "PHY"})

    for arm_id, subject_ids in (
        (science["id"], [maths["id"], physics["id"]]),
        (arts["id"], [maths["id"]]),
        (solo["id"], [maths["id"]]),
    ):
        for subject_id in subject_ids:
            _post(
                client,
                sid,
                f"{ACAD}/offerings",
                {"arm_id": arm_id, "subject_id": subject_id},
            )

    seed_grade_scale(db, sid)

    # Two pupils per arm, so a group-wide ranking has something to interleave.
    enrollments: dict[str, list[str]] = {}
    for arm_name, arm_id in (
        ("science", science["id"]),
        ("arts", arts["id"]),
        ("solo", solo["id"]),
    ):
        enrollments[arm_name] = []
        for i in (1, 2):
            student_id = _post(
                client,
                sid,
                "/api/students",
                {
                    "admission_no": f"{arm_name[:3].upper()}-{i}",
                    "first_name": f"{arm_name.title()}{i}",
                    "last_name": "Pupil",
                    "gender": "female" if i % 2 == 0 else "male",
                },
            )["id"]
            enrollments[arm_name].append(
                _post(
                    client,
                    sid,
                    "/api/students/enrollments",
                    {
                        "student_id": student_id,
                        "arm_id": arm_id,
                        "session_id": session_id,
                    },
                )["id"]
            )

    grant_permission(db, sid, "results.enter")

    return {
        "session_id": session_id,
        "term_id": term_id,
        "arms": {"science": science["id"], "arts": arts["id"], "solo": solo["id"]},
        "subjects": {"maths": maths["id"], "physics": physics["id"]},
        "enrollments": enrollments,
        "components": _add_components(client, sid, term_id),
    }


def _enter(client, sid, w, *, arm: str, subject: str, scores: list[int]) -> list[dict]:
    """Put one mark per pupil in an arm x subject cell and return the grid."""
    comps = w["components"]
    entries = [
        {
            "student_enrollment_id": env_id,
            "scores": [
                {"assessment_component_id": comps[name], "score": score}
                for name in ("CA1", "CA2", "Exam")
            ],
        }
        for env_id, score in zip(w["enrollments"][arm], scores)
    ]
    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arms"][arm],
            "subject_id": w["subjects"][subject],
            "term_id": w["term_id"],
            "entries": entries,
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    return r.json()["students"]


def _step(client, sid, w, action: str, *, arm: str, subject: str):
    r = client.post(
        f"{BASE}/{action}",
        json={
            "arm_id": w["arms"][arm],
            "subject_id": w["subjects"][subject],
            "term_id": w["term_id"],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _publish(client, sid, w, *, arm: str, subject: str) -> None:
    for step in ("submit", "verify", "approve", "publish"):
        _step(client, sid, w, step, arm=arm, subject=subject)


def _card(client, sid, w, student_id: str) -> dict:
    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": student_id, "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _student_id(db, enrollment_id: str) -> str:
    return str(db.get(StudentEnrollment, enrollment_id).student_id)


def _stored_positions(db, arm_id: str, subject_id: str, term_id: str) -> list[int]:
    rows = db.scalars(
        select(Result)
        .where(
            Result.class_arm_id == arm_id,
            Result.subject_id == subject_id,
            Result.term_id == term_id,
            Result.position.is_not(None),
        )
        .order_by(Result.position)
    ).all()
    return [row.position for row in rows]


def test_subject_positions_span_the_whole_group(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure_group(client, sid, db)

    # Science 90, 40; Arts 70, 20 — entered class by class, as a school does.
    _enter(client, sid, w, arm="science", subject="maths", scores=[90, 40])
    _enter(client, sid, w, arm="arts", subject="maths", scores=[70, 20])

    # A single 1..4 ranking with the two classes interleaved. Ranked per class,
    # the two would each run 1..2 and the Arts pupil on 70 would look like a
    # joint top of the year group.
    positions = {}
    for env_id, total in [
        (w["enrollments"]["science"][0], 90),
        (w["enrollments"]["science"][1], 40),
        (w["enrollments"]["arts"][0], 70),
        (w["enrollments"]["arts"][1], 20),
    ]:
        row = db.scalar(
            select(Result).where(
                Result.student_enrollment_id == env_id,
                Result.subject_id == w["subjects"]["maths"],
                Result.term_id == w["term_id"],
            )
        )
        assert float(row.total) == total
        positions[env_id] = row.position

    assert positions[w["enrollments"]["science"][0]] == 1
    assert positions[w["enrollments"]["arts"][0]] == 2
    assert positions[w["enrollments"]["science"][1]] == 3
    assert positions[w["enrollments"]["arts"][1]] == 4

    # A subject only one class offers is ranked within the pupils who take it.
    _enter(client, sid, w, arm="science", subject="physics", scores=[55, 65])
    assert _stored_positions(
        db, w["arms"]["science"], w["subjects"]["physics"], w["term_id"]
    ) == [1, 2]

    # The ungrouped control arm ranks alone, exactly as before.
    _enter(client, sid, w, arm="solo", subject="maths", scores=[30, 80])
    solo = {
        row.position
        for row in db.scalars(
            select(Result).where(
                Result.class_arm_id == w["arms"]["solo"],
                Result.subject_id == w["subjects"]["maths"],
                Result.term_id == w["term_id"],
            )
        )
    }
    assert solo == {1, 2}


def test_class_standing_ranks_by_average_over_the_group(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure_group(client, sid, db)

    # A Science pupil sits two subjects; an Arts pupil sits one. On the SUM of
    # totals the Science pupil would win 160 to 90 — that is the whole reason
    # the group standing is ranked on the average, and on the average the Arts
    # pupil wins 90 to 80.
    _enter(client, sid, w, arm="science", subject="maths", scores=[80, 10])
    _enter(client, sid, w, arm="science", subject="physics", scores=[80, 10])
    _enter(client, sid, w, arm="arts", subject="maths", scores=[90, 5])
    for arm, subject in (
        ("science", "maths"),
        ("science", "physics"),
        ("arts", "maths"),
    ):
        _publish(client, sid, w, arm=arm, subject=subject)

    science_card = _card(client, sid, w, _student_id(db, w["enrollments"]["science"][0]))
    assert science_card["summary"]["total"] == 160
    assert science_card["summary"]["average"] == 80

    arts_card = _card(client, sid, w, _student_id(db, w["enrollments"]["arts"][0]))
    assert arts_card["summary"]["total"] == 90
    assert arts_card["summary"]["average"] == 90

    # Six pupils sit Mathematics across the three arms, but only the five in
    # the group are counted against each other.
    assert science_card["summary"]["class_size"] == 4
    assert science_card["summary"]["class_group"] == GROUP
    assert arts_card["summary"]["class_rank"] == 1
    assert science_card["summary"]["class_rank"] == 2


def test_publishing_a_sibling_refreshes_earlier_group_positions(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure_group(client, sid, db)

    # Science is scored and published before Arts has any marks at all: its
    # cards freeze a standing out of 2.
    _enter(client, sid, w, arm="science", subject="maths", scores=[90, 40])
    _publish(client, sid, w, arm="science", subject="maths")

    science_student = _student_id(db, w["enrollments"]["science"][0])
    card = _card(client, sid, w, science_student)
    assert card["summary"]["class_size"] == 2
    assert [s["position"] for s in card["subjects"]] == [1]

    # Arts arrives. Publishing it re-ranks the whole group, and the class
    # already on the shelf has to agree — a card must not keep claiming a
    # standing out of 2 once the group is four.
    _enter(client, sid, w, arm="arts", subject="maths", scores=[70, 20])
    _publish(client, sid, w, arm="arts", subject="maths")

    refreshed = _card(client, sid, w, science_student)
    assert refreshed["summary"]["class_size"] == 4
    assert [s["position"] for s in refreshed["subjects"]] == [1]

    arts_card = _card(client, sid, w, _student_id(db, w["enrollments"]["arts"][0]))
    assert [s["position"] for s in arts_card["subjects"]] == [2]

    # Only the group-relative position is rewritten. Totals, grades and the
    # component scores stay exactly as published.
    row = db.scalar(
        select(Result).where(
            Result.student_enrollment_id == w["enrollments"]["science"][1],
            Result.subject_id == w["subjects"]["maths"],
            Result.term_id == w["term_id"],
        )
    )
    assert row.published_snapshot["total"] == 40.0
    assert row.published_snapshot["position"] == 3
    assert len(row.published_snapshot["components"]) == 3

    # The ungrouped control arm is never touched by the group's publishing.
    _enter(client, sid, w, arm="solo", subject="maths", scores=[30, 80])
    _publish(client, sid, w, arm="solo", subject="maths")
    solo_cards = client.get(
        f"{BASE}/report-cards",
        params={"arm_id": w["arms"]["solo"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert solo_cards.status_code == 200, solo_cards.text
    cards = solo_cards.json()
    assert len(cards) == 2
    assert all(card["summary"]["class_size"] == 2 for card in cards)
    assert all(card["summary"]["class_group"] is None for card in cards)


def test_group_broadsheet_covers_every_class_in_the_group(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure_group(client, sid, db)

    _enter(client, sid, w, arm="science", subject="maths", scores=[80, 10])
    _enter(client, sid, w, arm="science", subject="physics", scores=[80, 10])
    _enter(client, sid, w, arm="arts", subject="maths", scores=[90, 5])
    _enter(client, sid, w, arm="solo", subject="maths", scores=[30, 80])
    for arm, subject in (
        ("science", "maths"),
        ("science", "physics"),
        ("arts", "maths"),
        ("solo", "maths"),
    ):
        _publish(client, sid, w, arm=arm, subject=subject)

    r = client.get(
        f"{BASE}/broadsheet",
        params={
            "group_name": GROUP,
            "session_id": w["session_id"],
            "term_id": w["term_id"],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    cards = r.json()

    # All four pupils of the group, and none of the control arm's two.
    assert len(cards) == 4
    assert {card["class_arm"]["full_name"] for card in cards} == {"SS 1 Science", "SS 1 Arts"}

    # Ordered by group standing, so the sheet reads as one list.
    ranks = [card["summary"]["class_rank"] for card in cards]
    assert ranks == sorted(ranks)
    assert ranks[0] == 1

    # Each pupil carries their own subjects: the Science pair sit Physics, the
    # Arts pair do not — that blank is what makes it a group sheet rather than
    # three class sheets stapled together.
    science_cards = [c for c in cards if c["class_arm"]["full_name"] == "SS 1 Science"]
    arts_cards = [c for c in cards if c["class_arm"]["full_name"] == "SS 1 Arts"]
    assert all(len(c["subjects"]) == 2 for c in science_cards)
    assert all(len(c["subjects"]) == 1 for c in arts_cards)

    # A group nobody has is a 404, not an empty sheet.
    missing = client.get(
        f"{BASE}/broadsheet",
        params={
            "group_name": "SS 9",
            "session_id": w["session_id"],
            "term_id": w["term_id"],
        },
        headers={"X-School-Id": sid},
    )
    assert missing.status_code == 404


def test_broadsheet_by_arm_is_unchanged(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure_group(client, sid, db)

    _enter(client, sid, w, arm="science", subject="maths", scores=[80, 10])
    _publish(client, sid, w, arm="science", subject="maths")

    r = client.get(
        f"{BASE}/broadsheet",
        params={"arm_id": w["arms"]["science"], "term_id": w["term_id"]},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    cards = r.json()
    assert len(cards) == 2
    assert all(card["class_arm"]["full_name"] == "SS 1 Science" for card in cards)


def test_group_name_is_normalised_and_can_be_cleared(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure_group(client, sid, db)

    # Blank is "no group", not a group whose name is an empty string.
    arm = _post(
        client,
        sid,
        f"{ACAD}/arms",
        {
            "session_id": w["session_id"],
            "name": "SS 2 Science",
            "group_name": "   ",
        },
    )
    assert arm["group_name"] is None

    r = client.patch(
        f"{ACAD}/arms/{arm['id']}",
        json={"group_name": "  SS 2 "},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["group_name"] == "SS 2"

    # Renaming must not disturb the group it is already in.
    r = client.patch(
        f"{ACAD}/arms/{arm['id']}",
        json={"name": "SS 2A"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["group_name"] == "SS 2"

    # An explicit null clears it; omitting the field leaves it alone.
    r = client.patch(
        f"{ACAD}/arms/{arm['id']}",
        json={"group_name": None},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["group_name"] is None
    assert db.get(ClassArm, arm["id"]).group_name is None
