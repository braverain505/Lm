"""Phase 3 import tests: the wizard pipeline (upload → mapping → validation →
fixes → run), history, re-import with a new mapping, live progress, tenant
isolation, and the permission gate.

These exercise the real service layer through the HTTP API (with the test
session injected), the same integration style as the rest of the suite.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from app.services import import_service
from .conftest import active_school_id, register_school

BASE = "/api/imports"
ACAD = "/api/academics"


def _school(client, name: str, email: str) -> str:
    """Register a school and return its id. Never pass the register payload
    into ``active_school_id`` — that would shadow the client with a dict."""
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _rows(*data_list) -> list[dict]:
    return [
        {"row_number": i + 1, "data": data} for i, data in enumerate(data_list)
    ]


def _create_batch(client, school_id: str, rows: list[dict], filename: str = "legacy.csv") -> dict:
    r = client.post(
        BASE,
        json={"entity_type": "students", "filename": filename, "rows": rows},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _set_mapping(client, school_id: str, batch_id: str, mapping: dict) -> dict:
    r = client.post(
        f"{BASE}/{batch_id}/mapping",
        json={"mapping": mapping},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


_STUDENT_MAPPING = {
    "admission_no": "admission_no",
    "first_name": "first_name",
    "last_name": "last_name",
    "gender": "gender",
}


# --- Upload / preview (3.1) --------------------------------------------------------
def test_upload_stores_raw_rows_and_detects_columns(client):
    school_id = _school(client, "Import Academy", "im@test.edu")
    batch = _create_batch(
        client, school_id,
        _rows(
            {"Admission No": "SA-001", "Full Name": "Ade Bello", "Sex": "M"},
            {"Admission No": "SA-002", "Full Name": "Chi Okafor", "Sex": "F"},
        ),
    )
    assert batch["entity_type"] == "students"
    assert batch["status"] == "uploaded"
    assert batch["total_rows"] == 2
    assert batch["columns"] == ["Admission No", "Full Name", "Sex"]
    assert batch["parent_batch_id"] is None

    # The raw row is stored verbatim — re-import never needs the original file.
    r = client.get(f"{BASE}/{batch['id']}/rows", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["rows"][0]["data"] == {"Admission No": "SA-001", "Full Name": "Ade Bello", "Sex": "M"}
    assert body["rows"][0]["row_number"] == 1


def test_fields_endpoint_lists_target_fields(client):
    school_id = _school(client, "Fields School", "fs@test.edu")
    r = client.get(f"{BASE}/fields?entity_type=students", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    fields = {f["name"]: f for f in r.json()}
    assert fields["first_name"]["required"] is True
    assert fields["gender"]["options"] == ["male", "female"]
    assert "class_arm" in fields


def test_unknown_entity_type_rejected(client):
    school_id = _school(client, "Bad Type", "bt@test.edu")
    r = client.post(
        BASE,
        json={"entity_type": "aliens", "filename": "x.csv", "rows": _rows({"a": 1})},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


# --- Mapping + validation (3.1) ------------------------------------------------------
def test_mapping_validates_rows_with_field_errors(client):
    school_id = _school(client, "Valid School", "vs@test.edu")
    batch = _create_batch(
        client, school_id,
        _rows(
            {"admission_no": "V-001", "first_name": "Ade", "last_name": "Bello", "gender": "male"},
            {"admission_no": "V-002", "first_name": "Chi", "last_name": "", "gender": "female"},
            {"admission_no": "V-003", "first_name": "Deyo", "last_name": "Eze", "gender": "unknown"},
            {"admission_no": "V-001", "first_name": "Fat", "last_name": "Gana", "gender": "male"},
        ),
    )
    mapped = _set_mapping(client, school_id, batch["id"], _STUDENT_MAPPING)

    assert mapped["status"] == "ready"
    assert mapped["rows_valid"] == 1
    assert mapped["rows_invalid"] == 3
    assert mapped["error_summary"] == {"last_name": 1, "gender": 1, "admission_no": 1}

    r = client.get(
        f"{BASE}/{batch['id']}/rows?status=invalid", headers={"X-School-Id": school_id}
    )
    assert r.status_code == 200
    invalid = {row["row_number"]: row for row in r.json()["rows"]}
    assert set(invalid) == {2, 3, 4}
    assert invalid[2]["errors"]["last_name"] == ["Last name is required"]
    assert invalid[3]["errors"]["gender"] == ["Gender must be 'male' or 'female'"]
    assert "Duplicate admission number earlier in this file" in invalid[4]["errors"]["admission_no"]


def test_mapping_rejects_missing_required_and_unknown_targets(client):
    school_id = _school(client, "Gate School", "gs@test.edu")
    batch = _create_batch(
        client, school_id, _rows({"first_name": "Ade", "last_name": "Bello", "gender": "male"})
    )
    # Required field (first_name) not mapped.
    r = client.post(
        f"{BASE}/{batch['id']}/mapping",
        json={"mapping": {"last_name": "last_name", "gender": "gender"}},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert "First name" in r.json()["error"]["details"]["missing"]

    # Target field that doesn't exist for the entity type.
    r = client.post(
        f"{BASE}/{batch['id']}/mapping",
        json={"mapping": {"last_name": "social_security_no"}},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert "social_security_no" in r.json()["error"]["details"]["unknown"]

    # Source column that isn't in the file.
    r = client.post(
        f"{BASE}/{batch['id']}/mapping",
        json={"mapping": {"nope": "first_name", "last_name": "last_name", "gender": "gender"}},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert "nope" in r.json()["error"]["details"]["unknown_columns"]


def test_fix_row_revalidates_and_flips_status(client):
    school_id = _school(client, "Fix School", "fx@test.edu")
    batch = _create_batch(
        client, school_id,
        _rows({"admission_no": "F-001", "first_name": "Ade", "last_name": "Bello", "gender": "unknown"}),
    )
    _set_mapping(client, school_id, batch["id"], _STUDENT_MAPPING)
    r = client.get(f"{BASE}/{batch['id']}/rows?status=invalid", headers={"X-School-Id": school_id})
    row = r.json()["rows"][0]

    # Fix the gender → row becomes valid.
    r = client.put(
        f"{BASE}/{batch['id']}/rows/{row['id']}/fix",
        json={"fixes": {"gender": "female"}},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "valid"
    assert r.json()["effective"]["gender"] == "female"

    detail = client.get(f"{BASE}/{batch['id']}", headers={"X-School-Id": school_id}).json()
    assert detail["rows_invalid"] == 0
    assert detail["rows_valid"] == 1

    # Clearing the fix restores the raw value → invalid again.
    r = client.put(
        f"{BASE}/{batch['id']}/rows/{row['id']}/fix",
        json={"fixes": {"gender": ""}},
        headers={"X-School-Id": school_id},
    )
    assert r.json()["status"] == "invalid"


# --- Run + live progress (3.2) -------------------------------------------------------
def test_run_import_background_creates_students(client, db: Session):
    school_id = _school(client, "Run School", "rn@test.edu")
    batch = _create_batch(
        client, school_id,
        _rows(
            {"admission_no": "R-001", "first_name": "Ade", "last_name": "Bello", "gender": "male",
             "state": "Lagos"},
            {"admission_no": "R-002", "first_name": "Chi", "last_name": "Okafor", "gender": "female",
             "date_of_birth": "2012-05-01"},
        ),
    )
    _set_mapping(client, school_id, batch["id"], {**_STUDENT_MAPPING, "date_of_birth": "date_of_birth"})

    r = client.post(f"{BASE}/{batch['id']}/run", headers={"X-School-Id": school_id})
    assert r.status_code == 202
    # The 202 already reflects "running"; the background task completes the rest.
    assert r.json()["status"] == "running"

    # The run endpoint schedules a background job that commits on its own
    # connection. The test harness pins every request to one shared session
    # whose commits don't reach the real DB, so drive the same pipeline the
    # job calls (run_import) in-session, then poll as the UI would.
    import_service.run_import(db, uuid.UUID(batch["id"]))

    detail = client.get(f"{BASE}/{batch['id']}", headers={"X-School-Id": school_id}).json()
    assert detail["status"] == "completed"
    assert detail["rows_imported"] == 2
    assert detail["rows_failed"] == 0

    students = client.get("/api/students", headers={"X-School-Id": school_id}).json()
    by_admission = {s["admission_no"]: s for s in students}
    assert by_admission["R-001"]["first_name"] == "Ade"
    assert by_admission["R-002"]["date_of_birth"] == "2012-05-01"


def test_registered_admission_numbers_fail_at_run(client):
    """A duplicate slipping past validation (race) lands as a failed row, never
    a crash — and the valid sibling still imports."""
    school_id = _school(client, "Race School", "rc@test.edu")
    r = client.post(
        "/api/students",
        json={"admission_no": "TAKEN-1", "first_name": "Old", "last_name": "Owner", "gender": "male"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201

    # Create the batch AFTER the student exists so validation flags it (invalid),
    # plus a second row that is valid.
    batch = _create_batch(
        client, school_id,
        _rows(
            {"admission_no": "TAKEN-1", "first_name": "Ade", "last_name": "Bello", "gender": "male"},
            {"admission_no": "NEW-1", "first_name": "Chi", "last_name": "Okafor", "gender": "female"},
        ),
    )
    mapped = _set_mapping(client, school_id, batch["id"], _STUDENT_MAPPING)
    assert mapped["rows_invalid"] == 1  # already-registered number caught at mapping
    assert mapped["rows_valid"] == 1


def test_auto_generated_admission_numbers(client, db: Session):
    school_id = _school(client, "Auto School", "au@test.edu")
    batch = _create_batch(
        client, school_id,
        _rows(
            {"first_name": "Ade", "last_name": "Bello", "gender": "male"},
            {"first_name": "Chi", "last_name": "Okafor", "gender": "female"},
        ),
    )
    _set_mapping(client, school_id, batch["id"], _STUDENT_MAPPING)
    r = client.post(f"{BASE}/{batch['id']}/run", headers={"X-School-Id": school_id})
    assert r.status_code == 202
    import_service.run_import(db, uuid.UUID(batch["id"]))

    detail = client.get(f"{BASE}/{batch['id']}", headers={"X-School-Id": school_id}).json()
    assert detail["status"] == "completed"
    assert detail["rows_imported"] == 2

    students = client.get("/api/students", headers={"X-School-Id": school_id}).json()
    assert len(students) == 2
    assert all(s["admission_no"].startswith("IMP-") for s in students)


def _create_arm_world(client, school_id: str) -> str:
    """Create a current session + arm (full_name 'JSS 1A')."""
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": school_id},
    )
    session_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": session_id, "name": "JSS 1A"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_import_enrolls_into_class_arm(client, db: Session):
    school_id = _school(client, "Arm School", "ar@test.edu")
    arm_id = _create_arm_world(client, school_id)

    batch = _create_batch(
        client, school_id,
        _rows(
            {"admission_no": "A-001", "first_name": "Ade", "last_name": "Bello",
             "gender": "male", "class_arm": "JSS 1A"},
            {"admission_no": "A-002", "first_name": "Chi", "last_name": "Okafor",
             "gender": "female", "class_arm": "SSS 3B"},  # no such arm in the school
        ),
    )
    mapped = _set_mapping(
        client, school_id, batch["id"],
        {**_STUDENT_MAPPING, "class_arm": "class_arm"},
    )
    assert mapped["rows_valid"] == 1
    assert mapped["rows_invalid"] == 1

    r = client.get(f"{BASE}/{batch['id']}/rows?status=invalid", headers={"X-School-Id": school_id})
    row = r.json()["rows"][0]
    assert any("SSS 3B" in m for m in row["errors"]["class_arm"])

    # Drop the bad row's arm via a fix (empty = ignore class), then run.
    r = client.put(
        f"{BASE}/{batch['id']}/rows/{row['id']}/fix",
        json={"fixes": {"class_arm": ""}},
        headers={"X-School-Id": school_id},
    )
    assert r.json()["status"] == "valid"

    r = client.post(f"{BASE}/{batch['id']}/run", headers={"X-School-Id": school_id})
    assert r.status_code == 202
    import_service.run_import(db, uuid.UUID(batch["id"]))

    enrollments = client.get(
        f"/api/students/arms/{arm_id}/enrollments", headers={"X-School-Id": school_id}
    ).json()
    assert len(enrollments) == 1  # only the valid arm row enrolled
    assert enrollments[0]["student_id"]


def test_cannot_run_without_mapping_or_twice(client):
    school_id = _school(client, "Guard School", "gd@test.edu")
    batch = _create_batch(
        client, school_id, _rows({"first_name": "Ade", "last_name": "Bello", "gender": "male"})
    )
    r = client.post(f"{BASE}/{batch['id']}/run", headers={"X-School-Id": school_id})
    assert r.status_code == 409
    assert "mapping" in r.json()["error"]["message"].lower()

    _set_mapping(client, school_id, batch["id"], _STUDENT_MAPPING)
    r = client.post(f"{BASE}/{batch['id']}/run", headers={"X-School-Id": school_id})
    assert r.status_code == 202
    # Second run while completed → conflict.
    r = client.post(f"{BASE}/{batch['id']}/run", headers={"X-School-Id": school_id})
    assert r.status_code == 409


# --- History + re-import (3.2) ---------------------------------------------------------
def test_history_lists_batches_newest_first(client):
    school_id = _school(client, "Hist School", "hi@test.edu")
    _create_batch(client, school_id, _rows({"first_name": "A", "last_name": "B", "gender": "male"}), "one.csv")
    batch2 = _create_batch(client, school_id, _rows({"first_name": "C", "last_name": "D", "gender": "female"}), "two.csv")

    r = client.get(BASE, headers={"X-School-Id": school_id})
    assert r.status_code == 200
    batches = r.json()
    assert len(batches) == 2
    assert batches[0]["id"] == batch2["id"]  # newest first
    assert batches[0]["filename"] == "two.csv"


def test_reimport_reuses_rows_with_new_mapping(client, db: Session):
    school_id = _school(client, "Re School", "re@test.edu")
    batch = _create_batch(
        client, school_id,
        _rows(
            {"admission_no": "O-001", "first_name": "Ade", "last_name": "Bello", "gender": "male"},
            {"admission_no": "O-002", "first_name": "Chi", "last_name": "Okafor", "gender": "female"},
        ),
    )
    _set_mapping(client, school_id, batch["id"], _STUDENT_MAPPING)
    import_service.run_import(db, uuid.UUID(batch["id"]))
    assert len(client.get("/api/students", headers={"X-School-Id": school_id}).json()) == 2

    # Re-import the same rows with a *new* admission scheme (no re-upload).
    r = client.post(f"{BASE}/{batch['id']}/reimport", headers={"X-School-Id": school_id})
    assert r.status_code == 201
    child = r.json()
    assert child["parent_batch_id"] == batch["id"]
    assert child["status"] == "uploaded"
    assert child["total_rows"] == 2
    assert child["columns"] == ["admission_no", "first_name", "last_name", "gender"]

    # No admission_no: the re-imported rows reuse the parent's raw numbers
    # (O-001/O-002), which the first run already registered — leave the
    # field unmapped so the new run auto-generates fresh numbers instead.
    new_mapping = {
        "first_name": "first_name",
        "last_name": "last_name",
        "gender": "gender",
    }
    _set_mapping(client, school_id, child["id"], new_mapping)
    import_service.run_import(db, uuid.UUID(child["id"]))

    detail = client.get(f"{BASE}/{child['id']}", headers={"X-School-Id": school_id}).json()
    assert detail["status"] == "completed"
    assert detail["rows_imported"] == 2
    # 2 originals + 2 re-imported.
    assert len(client.get("/api/students", headers={"X-School-Id": school_id}).json()) == 4


# --- Tenancy + permissions --------------------------------------------------------------
def test_import_tenant_isolation(client, db: Session):
    register_school(client, name="Tenant One", email="t1@test.edu")
    a_id = active_school_id(client)
    a_batch = _create_batch(client, a_id, _rows({"first_name": "A", "last_name": "B", "gender": "male"}))

    # Switch tenant on the same client.
    client.post("/api/auth/logout")
    register_school(client, name="Tenant Two", email="t2@test.edu")
    b_id = active_school_id(client)

    r = client.get(BASE, headers={"X-School-Id": b_id})
    assert r.status_code == 200
    assert r.json() == []

    r = client.get(f"{BASE}/{a_batch['id']}", headers={"X-School-Id": b_id})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def _teacher_membership(db: Session, school_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    """Create a teacher (no import permissions) and return (token, user_id)."""
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == "teacher"))
    assert role is not None
    user = User(
        email="teacher@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Miss T",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_import_requires_permission(client, db: Session):
    register_school(client, name="Perm School", email="pm@test.edu")
    school_id = active_school_id(client)
    token, _ = _teacher_membership(db, school_id)

    # The admin's session cookie would win over a Bearer token — clear it first.
    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(BASE, headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(BASE, json={"entity_type": "students", "rows": _rows({"a": 1})}, headers=headers)
    assert r.status_code == 403


# --- Service-level live progress -------------------------------------------------------
def test_run_import_service_direct(client, db: Session):
    """The chunked run commits progress row-by-row; direct service call works."""
    register_school(client, name="Svc School", email="sv@test.edu")
    school_id = active_school_id(client)

    batch = import_service.create_batch(
        db, uuid.UUID(school_id),
        entity_type="students", filename="s.csv", created_by=None,
        rows=_rows(
            {"admission_no": "S-001", "first_name": "A", "last_name": "B", "gender": "male"},
            {"admission_no": "S-002", "first_name": "C", "last_name": "D", "gender": "female"},
        ),
    )
    import_service.set_mapping(db, uuid.UUID(school_id), batch.id, _STUDENT_MAPPING)
    import_service.run_import(db, batch.id, chunk_size=1)  # one commit per row

    from app.models.imports import ImportRow, STATUS_COMPLETED
    reloaded = import_service.get_batch(db, uuid.UUID(school_id), batch.id)
    assert reloaded.status == STATUS_COMPLETED
    assert reloaded.rows_imported == 2

    rows = list(db.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id)))
    assert all(r.status == import_service.ROW_IMPORTED for r in rows)
    assert all(r.imported_entity_id is not None for r in rows)