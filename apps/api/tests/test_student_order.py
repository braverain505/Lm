"""Pupil order: rosters and score grids follow the school's chosen key.

The grid used to be ordered by the enrolment's UUID, which is to say at random,
and the roster had one fixed order. A register is read by name, so both now follow
one choice — surname (the default), first name, or admission number — and the
comparison ignores case, because hand-typed registers never agree on it.
"""
from __future__ import annotations

import uuid

from .conftest import active_school_id, register_school

STUDENTS = "/api/students"
ACAD = "/api/academics"
RESULTS = "/api/results"

PUPILS = [
    ("S-003", "zara", "Adeyemi"),      # lower case on purpose
    ("S-001", "Grace", "Adamu"),
    ("S-002", "Peter", "Yakubu"),
]


def _school_with_pupils(client) -> dict:
    register_school(client)
    sid = active_school_id(client)
    headers = {"X-School-Id": sid}

    session = client.post(
        f"{ACAD}/sessions", json={"name": "2025/2026", "is_current": True}, headers=headers
    ).json()
    term = client.post(
        f"{ACAD}/terms",
        json={"session_id": session["id"], "term_no": 1, "name": "First Term"},
        headers=headers,
    ).json()
    client.post(f"{ACAD}/sessions/{session['id']}/activate", headers=headers)
    client.post(f"{ACAD}/terms/{term['id']}/activate", headers=headers)
    arm = client.post(
        f"{ACAD}/arms", json={"session_id": session["id"], "name": "JSS 1 A"}, headers=headers
    ).json()
    subject = client.post(
        f"{ACAD}/subjects", json={"name": "Mathematics", "code": "MTH"}, headers=headers
    ).json()
    client.post(
        f"{ACAD}/offerings",
        json={"arm_id": arm["id"], "subject_id": subject["id"]},
        headers=headers,
    )

    created = []
    for admission, first, last in PUPILS:
        student = client.post(
            STUDENTS,
            json={
                "admission_no": admission,
                "first_name": first,
                "last_name": last,
                "gender": "female",
            },
            headers=headers,
        ).json()
        client.post(
            f"{STUDENTS}/enrollments",
            json={
                "student_id": student["id"],
                "arm_id": arm["id"],
                "session_id": session["id"],
            },
            headers=headers,
        )
        created.append(student)

    return {
        "sid": sid,
        "headers": headers,
        "arm_id": arm["id"],
        "subject_id": subject["id"],
        "term_id": term["id"],
        "pupils": created,
    }


def test_the_roster_is_ordered_by_surname_by_default(client):
    world = _school_with_pupils(client)
    rows = client.get(STUDENTS, headers=world["headers"]).json()
    assert [row["last_name"] for row in rows] == ["Adamu", "Adeyemi", "Yakubu"]


def test_the_order_can_be_chosen(client):
    world = _school_with_pupils(client)

    by_first = client.get(STUDENTS, params={"sort": "first_name"}, headers=world["headers"]).json()
    assert [row["first_name"] for row in by_first] == ["Grace", "Peter", "zara"]

    by_admission = client.get(STUDENTS, params={"sort": "admission"}, headers=world["headers"]).json()
    assert [row["admission_no"] for row in by_admission] == ["S-001", "S-002", "S-003"]

    # An unknown key falls back to the default rather than failing the request.
    fallback = client.get(STUDENTS, params={"sort": "banana"}, headers=world["headers"]).json()
    assert [row["last_name"] for row in fallback] == ["Adamu", "Adeyemi", "Yakubu"]


def test_case_does_not_decide_the_order(client):
    """Hand-typed registers mix cases; 'adeyemi' must still sit under A."""
    world = _school_with_pupils(client)
    rows = client.get(STUDENTS, headers=world["headers"]).json()
    assert rows[1]["last_name"] == "Adeyemi"  # not pushed below the capitals


def test_the_score_grid_follows_the_same_order(client, db):
    world = _school_with_pupils(client)
    arm_id = uuid.UUID(world["arm_id"])

    default = client.get(
        f"{RESULTS}/scorecard",
        params={
            "arm_id": world["arm_id"],
            "subject_id": world["subject_id"],
            "term_id": world["term_id"],
        },
        headers=world["headers"],
    )
    assert default.status_code == 200, default.text
    # Surname order, not the order the pupils happened to be created in.
    assert [row["full_name"] for row in default.json()["students"]] == [
        "Grace Adamu", "zara Adeyemi", "Peter Yakubu",
    ]

    by_first = client.get(
        f"{RESULTS}/scorecard",
        params={
            "arm_id": world["arm_id"],
            "subject_id": world["subject_id"],
            "term_id": world["term_id"],
            "sort": "first_name",
        },
        headers=world["headers"],
    )
    assert [row["full_name"] for row in by_first.json()["students"]] == [
        "Grace Adamu", "Peter Yakubu", "zara Adeyemi",
    ]