"""Sections: nursery, primary, secondary.

A school picks once whether every class follows one structure or each section
has its own — scoresheet and report card style together. These tests cover the
switch, the per-section scoresheet resolution, the fallback for a section with
no set of its own, switching back, a class's section (suggested from its name),
per-section report card designs, and reading the scoresheet shape that existed
before sections did.
"""
import uuid

import pytest

from app.services import sections_service
from app.services.results_service import _clean_scoresheet
from .conftest import active_school_id, register_school
from .test_report_card_templates import TEMPLATES, _create, _layout
from .test_results import (
    _act,
    _add_components,
    _configure,
    _enter_all,
)

BASE = "/api/results"
ACAD = "/api/academics"


def _put(client, school_id, rows, *, mode="same", sections=None):
    return client.put(
        f"{BASE}/scoresheet",
        json={"mode": mode, "default": rows, "sections": sections or {}},
        headers={"X-School-Id": school_id},
    )


def _arm_components(client, school_id, term_id, arm_id):
    r = client.get(
        f"{BASE}/components?term_id={term_id}&arm_id={arm_id}",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _make_arm(client, sid, session_id, name, **extra):
    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": session_id, "name": name, **extra},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- The switch -----------------------------------------------------------------
def test_a_school_starts_with_one_structure_for_every_class(client, db):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    body = client.get(f"{BASE}/scoresheet", headers={"X-School-Id": sid}).json()
    assert body["mode"] == "same"
    # Every section shows what it would use until the school says otherwise.
    for section in ("nursery", "primary", "secondary"):
        assert [row["name"] for row in body["sections"][section]] == [
            "1st CA", "2nd CA", "Exam",
        ]
    assert body["report_cards"]["primary"] == {
        "template_id": None, "name": None, "applied": False,
    }


def test_separate_sections_give_each_its_own_scoresheet(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    r = _put(
        client, sid,
        [{"name": "1st CA", "max_score": 20},
         {"name": "2nd CA", "max_score": 20},
         {"name": "Exam", "max_score": 60}],
        mode="separate",
        sections={"primary": [
            {"name": "1st CA", "max_score": 10},
            {"name": "2nd CA", "max_score": 10},
            {"name": "3rd CA", "max_score": 10},
            {"name": "Exam", "max_score": 70},
        ]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "separate"
    assert [row["name"] for row in body["sections"]["primary"]] == [
        "1st CA", "2nd CA", "3rd CA", "Exam",
    ]
    # A section with no set of its own shows the school-wide one it inherits.
    assert [row["name"] for row in body["sections"]["secondary"]] == [
        "1st CA", "2nd CA", "Exam",
    ]

    primary = _make_arm(client, sid, cfg["session_id"], "Primary 4", section="primary")
    secondary = _make_arm(client, sid, cfg["session_id"], "JSS 4 B", section="secondary")

    assert [c["name"] for c in _arm_components(
        client, sid, cfg["term_id"], primary["id"]
    )] == ["1st CA", "2nd CA", "3rd CA", "Exam"]
    # The original arm was created before the switch and was seeded school-wide;
    # a class in a section without its own set uses the school-wide set.
    assert [c["name"] for c in _arm_components(
        client, sid, cfg["term_id"], secondary["id"]
    )] == ["1st CA", "2nd CA", "Exam"]


def test_switching_back_to_same_ignores_the_section_sets(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    shared = [{"name": "1st CA", "max_score": 20},
              {"name": "2nd CA", "max_score": 20},
              {"name": "Exam", "max_score": 60}]
    separate = [{"name": "1st CA", "max_score": 10},
                {"name": "2nd CA", "max_score": 10},
                {"name": "3rd CA", "max_score": 10},
                {"name": "Exam", "max_score": 70}]

    r = _put(client, sid, shared, mode="separate",
             sections={"primary": separate})
    assert r.status_code == 200, r.text
    primary = _make_arm(client, sid, cfg["session_id"], "Primary 4", section="primary")
    assert len(_arm_components(client, sid, cfg["term_id"], primary["id"])) == 4

    r = _put(client, sid, shared, mode="separate", sections={"primary": separate})
    assert r.status_code == 200, r.text
    r = _put(client, sid, shared, mode="same", sections={"primary": separate})
    assert r.status_code == 200, r.text

    # The primary class is back on the school-wide structure, even though the
    # primary rows still exist for when the school switches back.
    assert [c["name"] for c in _arm_components(
        client, sid, cfg["term_id"], primary["id"]
    )] == ["1st CA", "2nd CA", "Exam"]


def test_an_invalid_mode_is_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    r = _put(client, sid, [{"name": "Exam", "max_score": 100}], mode="sometimes")
    assert r.status_code == 422, r.text


def test_a_section_needs_a_valid_scoresheet_of_its_own(client, db):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    r = _put(client, sid, [{"name": "Exam", "max_score": 100}], mode="separate",
             sections={"primary": []})
    assert r.status_code == 422, r.text
    assert "primary" in r.json()["error"]["message"].lower()


# --- A class's section ----------------------------------------------------------
def test_a_class_section_is_suggested_from_its_name(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    jss = _make_arm(client, sid, cfg["session_id"], "JSS 2A")
    assert jss["section"] == "secondary"
    nursery = _make_arm(client, sid, cfg["session_id"], "Nursery 1")
    assert nursery["section"] == "nursery"
    basic = _make_arm(client, sid, cfg["session_id"], "Basic 5")
    assert basic["section"] == "primary"
    # A name that says nothing leaves the class unclassified rather than
    # guessing.
    plain = _make_arm(client, sid, cfg["session_id"], "Gold")
    assert plain["section"] is None


def test_a_class_section_can_be_set_and_cleared(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)
    arm = _make_arm(client, sid, cfg["session_id"], "Gold", section="primary")

    r = client.patch(
        f"{ACAD}/arms/{arm['id']}",
        json={"section": "secondary"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["section"] == "secondary"

    # An omitted section leaves it alone; an explicit null clears it.
    r = client.patch(
        f"{ACAD}/arms/{arm['id']}", json={"name": "Gold 1"},
        headers={"X-School-Id": sid},
    )
    assert r.json()["section"] == "secondary"
    r = client.patch(
        f"{ACAD}/arms/{arm['id']}", json={"section": None},
        headers={"X-School-Id": sid},
    )
    assert r.json()["section"] is None


def test_an_unknown_section_is_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": cfg["session_id"], "name": "Gold", "section": "tertiary"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422, r.text


def test_guess_section_reads_the_class_name():
    assert sections_service.guess_section("JSS 1A") == "secondary"
    assert sections_service.guess_section("SS 2 Science") == "secondary"
    assert sections_service.guess_section("Pre-Nursery") == "nursery"
    assert sections_service.guess_section("KG 2") == "nursery"
    assert sections_service.guess_section("Primary 6") == "primary"
    assert sections_service.guess_section("Basic 3B") == "primary"
    assert sections_service.guess_section("Gold") is None
    assert sections_service.guess_section("") is None


# --- Report card style ----------------------------------------------------------
def test_each_section_can_draw_its_own_card(client, db):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    school_card = _create(client, sid, "Secondary card", is_default=True).json()
    primary_card = _create(
        client, sid, "Primary card", layout=_layout(theme="elegant")
    ).json()

    # Same mode: the section's pin is not in force yet.
    r = client.get(
        f"{TEMPLATES}/default?section=primary", headers={"X-School-Id": sid}
    )
    assert r.status_code == 200, r.text
    assert r.json()["template_id"] == school_card["id"]

    r = client.put(
        f"{TEMPLATES}/section-defaults",
        json={"designs": {"primary": primary_card["id"]}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    # Stored straight away, and named as the section's own...
    assert r.json()["primary"]["template_id"] == primary_card["id"]
    # ...but not in force while the school keeps one structure for every class.
    assert r.json()["primary"]["applied"] is False
    # An unpinned section follows the school default, named so the UI can say
    # which design it is falling back to.
    assert r.json()["secondary"] == {
        "template_id": None, "name": "Secondary card", "applied": False,
    }

    # Still "same": every class draws the school card.
    r = client.get(
        f"{TEMPLATES}/default?section=primary", headers={"X-School-Id": sid}
    )
    assert r.json()["template_id"] == school_card["id"]

    _put(client, sid, [{"name": "Exam", "max_score": 100}], mode="separate")

    assert client.get(
        f"{TEMPLATES}/section-defaults", headers={"X-School-Id": sid}
    ).json()["primary"]["applied"] is True
    r = client.get(
        f"{TEMPLATES}/default?section=primary", headers={"X-School-Id": sid}
    )
    assert r.json()["template_id"] == primary_card["id"]
    assert r.json()["layout"]["theme"] == "elegant"
    r = client.get(
        f"{TEMPLATES}/default?section=secondary", headers={"X-School-Id": sid}
    )
    assert r.json()["template_id"] == school_card["id"]

    # Clearing the pin puts the section back on the school default.
    r = client.put(
        f"{TEMPLATES}/section-defaults",
        json={"designs": {"primary": None}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["primary"]["template_id"] is None
    r = client.get(
        f"{TEMPLATES}/default?section=primary", headers={"X-School-Id": sid}
    )
    assert r.json()["template_id"] == school_card["id"]


def test_a_section_cannot_borrow_another_schools_card(client, db):
    register_school(client)
    sid = active_school_id(client)
    _configure(client, sid, db)

    other = register_school(client, name="Other Academy", email="o@o.edu")
    other_sid = active_school_id(client)
    foreign = _create(client, other_sid, "Their card").json()
    del other

    r = client.put(
        f"{TEMPLATES}/section-defaults",
        json={"designs": {"primary": foreign["id"]}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 404, r.text


# --- The stored shape -----------------------------------------------------------
def test_a_scoresheet_saved_before_sections_reads_as_school_wide():
    legacy = [
        {"name": "1st CA", "max_score": 20, "weight": 20},
        {"name": "Exam", "max_score": 80, "weight": 80},
    ]
    cleaned = _clean_scoresheet(legacy)
    assert [row["name"] for row in cleaned["default"]] == ["1st CA", "Exam"]
    assert cleaned["sections"] == {}


def test_a_malformed_stored_scoresheet_falls_back_to_the_builtin():
    assert _clean_scoresheet({"default": [{"name": "", "max_score": 10}]}) is None
    assert _clean_scoresheet({"sections": {}}) is None
    assert _clean_scoresheet("nonsense") is None

# --- Where a section's structure is actually used -------------------------------
def _publish_the_term(client, sid, cfg):
    """Take the configured class's one subject all the way to published."""
    comps = _add_components(client, sid, cfg["term_id"])
    _enter_all(client, sid, cfg, comps)
    for step in ("submit", "verify", "approve", "publish"):
        r = _act(client, sid, cfg, step)
        assert r.status_code == 200, r.text


def test_an_archived_term_freezes_each_sections_card(client, db):
    register_school(client)
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    _create(client, sid, "Secondary card", is_default=True)
    primary_card = _create(
        client, sid, "Primary card", layout=_layout(theme="elegant")
    ).json()

    _publish_the_term(client, sid, cfg)

    # The school decides on sections after the term is out, so its components
    # are left exactly as they were.
    r = _put(
        client, sid,
        [{"name": "1st CA", "max_score": 20},
         {"name": "2nd CA", "max_score": 20},
         {"name": "Exam", "max_score": 60}],
        mode="separate",
    )
    assert r.status_code == 200 and r.json()["locked"] is True, r.text
    r = client.put(
        f"{TEMPLATES}/section-defaults",
        json={"designs": {"primary": primary_card["id"]}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"{ACAD}/terms/{cfg['term_id']}/close",
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"{BASE}/archives?session_id={cfg['session_id']}",
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    archive_id = r.json()[0]["id"]
    r = client.get(f"{BASE}/archives/{archive_id}", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    layouts = r.json()["payload"]["layouts"]
    assert set(layouts) == {"nursery", "primary", "secondary"}
    # Every section's frozen design is the app's own, with the school-wide one
    # for the sections that follow it.
    assert layouts["primary"]["theme"] == "elegant"
    assert layouts["secondary"]["theme"] == layouts["nursery"]["theme"] != "elegant"


def test_a_childs_portal_card_follows_their_section(client, db):
    """A parent's copy is the card their child's section prints with, so it
    matches the one the exam office hands over."""
    register_school(client, name="Green Valley Grammar School")
    sid = active_school_id(client)
    cfg = _configure(client, sid, db)

    # The class is a primary one — the name alone does not say so.
    r = client.patch(
        f"{ACAD}/arms/{cfg['arm_id']}",
        json={"section": "primary"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    _create(client, sid, "School card", is_default=True)
    primary_card = _create(
        client, sid, "Primary card", layout=_layout(theme="elegant")
    ).json()

    _publish_the_term(client, sid, cfg)

    r = _put(
        client, sid,
        [{"name": "1st CA", "max_score": 20},
         {"name": "2nd CA", "max_score": 20},
         {"name": "Exam", "max_score": 60}],
        mode="separate",
    )
    assert r.status_code == 200, r.text
    r = client.put(
        f"{TEMPLATES}/section-defaults",
        json={"designs": {"primary": primary_card["id"]}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text

    code = client.post(
        "/api/results/portal-pin", headers={"X-School-Id": sid}
    ).json()["code"]
    r = client.post(
        "/api/public/result-check", json={"pin": code, "admission_no": "STU-001"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["report_template"]["theme"] == "elegant"
