"""Report card design tests: the drag-and-drop builder's backing store.

Pinned behavior:

* Designing a card is ``school.manage`` — the school admin's capability. Reading
  a design is open to any member of the school (a teacher opening a card has to
  draw it); a *different* school gets a neutral 404, never a design.
* A school that has saved nothing still gets a complete card: ``/default``
  answers with the built-in layout and ``builtin: true``, and that layout has the
  widgets the app drew before the designer existed.
* One default always: the first design becomes the default automatically, setting
  a default clears the other, clearing the default outright is refused, and
  deleting the default promotes a successor.
* The layout contract is enforced at the edge — unknown widget types, unknown
  themes, duplicate widget ids and markup in school-authored text are rejected
  with 422 rather than stored.
* The public portal hands the parent the same design the exam office prints.
"""
import uuid

from sqlalchemy import select

from app.models import AuditLog, ReportCardTemplate
from app.schemas.report_card import WIDGET_TYPES
from app.services.report_card_service import BUILTIN_DEFAULT_LAYOUT, builtin_layout
from .conftest import active_school_id, register_school
from .test_portal import _add_limited_user, _configure

TEMPLATES = "/api/report-card-templates"


def _layout(widgets=("header", "cognitive_domain"), theme="modern"):
    return {
        "version": 1,
        "theme": theme,
        "widgets": [
            {"id": f"w{i}", "type": t, "props": {}, "hidden": False}
            for i, t in enumerate(widgets)
        ],
    }


def _create(client, sid, name="Primary card", **overrides):
    body = {"name": name, "layout": _layout(), **overrides}
    return client.post(TEMPLATES, json=body, headers={"X-School-Id": sid})


def _login_as(client, db, sid, role_code):
    user = _add_limited_user(db, sid, role_code)
    r = client.post(
        "/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"}
    )
    assert r.status_code == 200, r.text
    return user


# --- Permission gating ----------------------------------------------------------
def test_writes_require_school_manage(client, db):
    register_school(client)
    sid = active_school_id(client)

    r = client.post(TEMPLATES, json={"name": "x", "layout": _layout()})
    assert r.status_code == 401  # no X-School-Id, no session

    _login_as(client, db, sid, "teacher")
    r = _create(client, sid)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


def test_reads_are_open_to_any_member(client, db):
    register_school(client)
    sid = active_school_id(client)
    assert _create(client, sid).status_code == 201

    # A teacher cannot create one, but must be able to read the design — it is
    # a document layout, not student data, and their card render needs it.
    _login_as(client, db, sid, "teacher")
    r = client.get(TEMPLATES, headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text
    assert [t["name"] for t in r.json()] == ["Primary card"]


def test_designs_are_tenant_isolated(client, db):
    register_school(client, name="School A", email="a@school.edu")
    sid_a = active_school_id(client)
    template_id = _create(client, sid_a).json()["id"]

    register_school(client, name="School B", email="b@school.edu")
    sid_b = active_school_id(client)

    r = client.get(f"{TEMPLATES}/{template_id}", headers={"X-School-Id": sid_b})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"
    # ...and school B never sees A's design in its own list.
    assert client.get(TEMPLATES, headers={"X-School-Id": sid_b}).json() == []


# --- The built-in card ----------------------------------------------------------
def test_default_falls_back_to_the_builtin_card(client, db):
    register_school(client)
    sid = active_school_id(client)

    body = client.get(f"{TEMPLATES}/default", headers={"X-School-Id": sid}).json()
    assert body["builtin"] is True
    assert body["template_id"] is None
    # The fallback is the card the app drew before the designer existed, so a
    # school that never opens the designer is not downgraded.
    assert [w["type"] for w in body["layout"]["widgets"]] == [
        w["type"] for w in BUILTIN_DEFAULT_LAYOUT["widgets"]
    ]
    assert body["layout"]["theme"] == "classic"


def test_every_builtin_widget_is_a_known_type():
    for widget in BUILTIN_DEFAULT_LAYOUT["widgets"]:
        assert widget["type"] in WIDGET_TYPES


def test_builtin_layout_is_returned_by_value():
    """Mutating what a caller received must not corrupt the process-wide fallback."""
    first = builtin_layout()
    first["widgets"].clear()
    assert len(builtin_layout()["widgets"]) == len(BUILTIN_DEFAULT_LAYOUT["widgets"])


# --- One default, always --------------------------------------------------------
def test_first_design_becomes_default_then_moving_it(client, db):
    register_school(client)
    sid = active_school_id(client)

    first = _create(client, sid, "Primary card").json()
    assert first["is_default"] is True  # automatic for the first design

    second = _create(client, sid, "Secondary card").json()
    assert second["is_default"] is False  # later designs do not steal it

    r = client.post(f"{TEMPLATES}/{second['id']}/default", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text

    listed = {t["name"]: t["is_default"] for t in client.get(
        TEMPLATES, headers={"X-School-Id": sid}
    ).json()}
    assert listed == {"Primary card": False, "Secondary card": True}
    assert client.get(f"{TEMPLATES}/default", headers={"X-School-Id": sid}).json()[
        "name"
    ] == "Secondary card"


def test_patching_is_default_true_moves_the_flag(client, db):
    register_school(client)
    sid = active_school_id(client)
    first = _create(client, sid, "One").json()
    second = _create(client, sid, "Two").json()

    r = client.patch(
        f"{TEMPLATES}/{second['id']}",
        json={"is_default": True},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_default"] is True

    defaults = db.scalars(
        select(ReportCardTemplate).where(
            ReportCardTemplate.school_id == sid, ReportCardTemplate.is_default.is_(True)
        )
    ).all()
    assert [t.name for t in defaults] == ["Two"]
    assert db.get(ReportCardTemplate, first["id"]).is_default is False


def test_cannot_clear_the_default_outright(client, db):
    register_school(client)
    sid = active_school_id(client)
    only = _create(client, sid, "Only").json()

    r = client.patch(
        f"{TEMPLATES}/{only['id']}",
        json={"is_default": False},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422
    # Name a successor instead.
    other = _create(client, sid, "Other").json()
    r = client.patch(
        f"{TEMPLATES}/{other['id']}",
        json={"is_default": True},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 200
    assert client.get(f"{TEMPLATES}/default", headers={"X-School-Id": sid}).json()[
        "name"
    ] == "Other"


def test_deleting_the_default_promotes_a_successor(client, db):
    register_school(client)
    sid = active_school_id(client)
    first = _create(client, sid, "One").json()
    second = _create(client, sid, "Two").json()

    r = client.delete(f"{TEMPLATES}/{second['id']}", headers={"X-School-Id": sid})
    assert r.status_code == 204

    remaining = client.get(f"{TEMPLATES}/default", headers={"X-School-Id": sid}).json()
    assert remaining["template_id"] == first["id"]

    # Deleting the last design drops the school back to the built-in card, not
    # to "no card".
    assert client.delete(
        f"{TEMPLATES}/{first['id']}", headers={"X-School-Id": sid}
    ).status_code == 204
    fallback = client.get(f"{TEMPLATES}/default", headers={"X-School-Id": sid}).json()
    assert fallback["builtin"] is True


def test_duplicate_names_copied_design(client, db):
    register_school(client)
    sid = active_school_id(client)
    source = _create(client, sid, "Primary card").json()

    r = client.post(f"{TEMPLATES}/{source['id']}/duplicate", headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    copy = r.json()
    assert copy["name"] == "Primary card (copy)"
    assert copy["is_default"] is False  # a copy never takes over silently
    assert copy["layout"] == source["layout"]


# --- Validation -----------------------------------------------------------------
def test_name_must_be_unique(client, db):
    register_school(client)
    sid = active_school_id(client)
    assert _create(client, sid, "Clash").status_code == 201
    r = _create(client, sid, "Clash")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"


def test_unknown_widget_type_is_rejected(client, db):
    """A design may only reference a widget the app can actually render."""
    register_school(client)
    sid = active_school_id(client)
    body = {"name": "Bad", "layout": _layout(widgets=("header", "not_a_widget"))}
    r = client.post(TEMPLATES, json=body, headers={"X-School-Id": sid})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"
    # The offending field is named so the designer can point at it.
    assert any("not_a_widget" in str(v) for v in r.json()["error"]["details"].values())


def test_unknown_theme_is_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    body = {"name": "Bad", "layout": _layout(theme="neon")}
    r = client.post(TEMPLATES, json=body, headers={"X-School-Id": sid})
    assert r.status_code == 422


def test_duplicate_widget_ids_are_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    body = {
        "name": "Bad",
        "layout": {
            "theme": "classic",
            "widgets": [
                {"id": "same", "type": "header"},
                {"id": "same", "type": "comments"},
            ],
        },
    }
    r = client.post(TEMPLATES, json=body, headers={"X-School-Id": sid})
    assert r.status_code == 422
    assert any("unique" in str(v).lower() for v in r.json()["error"]["details"].values())


def test_empty_widget_list_is_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    r = client.post(
        TEMPLATES,
        json={"name": "Empty", "layout": {"theme": "classic", "widgets": []}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422


def test_markup_in_school_text_is_stripped(client, db):
    register_school(client)
    sid = active_school_id(client)
    body = {
        "name": "Notice card",
        "description": "<script>alert(1)</script>Termly notice",
        "layout": {
            "theme": "classic",
            "widgets": [
                {"id": "h", "type": "header"},
                {
                    "id": "note",
                    "type": "custom_text",
                    "props": {"title": "<b>Rules</b>", "body": "<i>Be punctual</i>"},
                },
            ],
        },
    }
    r = client.post(TEMPLATES, json=body, headers={"X-School-Id": sid})
    assert r.status_code == 201, r.text
    stored = r.json()
    assert stored["description"] == "Termly notice"
    note = stored["layout"]["widgets"][1]["props"]
    # Tags are stripped, but the text is NOT HTML-escaped: the card renders it as
    # a React text node, so escaping here would print "&amp;" on a parent's card.
    assert note["title"] == "Rules"
    assert note["body"] == "Be punctual"


def test_oversized_layout_is_rejected(client, db):
    register_school(client)
    sid = active_school_id(client)
    widgets = [{"id": f"w{i}", "type": "spacer"} for i in range(50)]
    r = client.post(
        TEMPLATES,
        json={"name": "Huge", "layout": {"theme": "classic", "widgets": widgets}},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 422


# --- Renderer-facing read -------------------------------------------------------
def test_default_returns_the_saved_layout(client, db):
    register_school(client)
    sid = active_school_id(client)
    saved = _create(client, sid, "Custom", layout=_layout(theme="elegant")).json()

    body = client.get(f"{TEMPLATES}/default", headers={"X-School-Id": sid}).json()
    assert body["builtin"] is False
    assert body["template_id"] == saved["id"]
    assert body["theme"] == "elegant"
    assert [w["type"] for w in body["layout"]["widgets"]] == ["header", "cognitive_domain"]


def test_public_portal_carries_the_school_design(client, db):
    """The parent's card and the exam office's card must be the same document."""
    register_school(client)
    sid = active_school_id(client)
    _create(client, sid, "Custom", layout=_layout(theme="minimal"))
    w = _configure(client, sid, db)

    # Issue a per-student code through the API the exam office uses.
    r = client.post(
        f"/api/results/portal-codes/{w['student_ids'][0]}",
        headers={"X-School-Id": sid},
    )
    assert r.status_code in (200, 201), r.text
    code = r.json()["code"]

    check = client.post("/api/public/result-check", json={"pin": code})
    assert check.status_code == 200, check.text
    template = check.json()["report_template"]
    assert template["theme"] == "minimal"
    assert [x["type"] for x in template["widgets"]] == ["header", "cognitive_domain"]


# --- Audit trail ----------------------------------------------------------------
def test_design_changes_are_audited(client, db):
    register_school(client)
    sid = active_school_id(client)
    created = _create(client, sid, "Audited").json()
    client.patch(
        f"{TEMPLATES}/{created['id']}",
        json={"name": "Audited v2"},
        headers={"X-School-Id": sid},
    )
    client.delete(f"{TEMPLATES}/{created['id']}", headers={"X-School-Id": sid})

    rows = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.school_id == sid,
                AuditLog.entity_type == "report_card_template",
            )
        )
    )
    assert [r.action for r in rows] == ["create", "update", "delete"]
    assert {r.new.get("operation") for r in rows if r.new} == {"create", "update"}
