"""Inventory tests: categories, items, stock movements, tenant isolation, and
the permission gate — exercised through the real HTTP API.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/inventory"


def _school(client, name: str, email: str) -> str:
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _create_category(client, school_id: str, name: str) -> dict:
    r = client.post(
        f"{BASE}/categories",
        json={"name": name, "description": f"{name} category"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_item(
    client, school_id: str, name: str, quantity: float = 10.0, **extra
) -> dict:
    payload = {"name": name, "quantity": quantity, "unit": "pcs", "unit_cost": 500.0, **extra}
    r = client.post(
        f"{BASE}/items", json=payload, headers={"X-School-Id": school_id}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _adjust_stock(client, school_id: str, item_id: str, delta: float, mtype: str) -> dict:
    r = client.post(
        f"{BASE}/movements",
        json={"item_id": item_id, "delta": delta, "movement_type": mtype, "reason": "test"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- Categories -----------------------------------------------------------------
def test_create_list_and_update_categories(client):
    school_id = _school(client, "Inv School", "inv@test.edu")
    _create_category(client, school_id, "Stationery")
    _create_category(client, school_id, "ICT")

    r = client.get(f"{BASE}/categories", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    assert {c["name"] for c in r.json()} == {"Stationery", "ICT"}

    first = r.json()[0]
    r = client.put(
        f"{BASE}/categories/{first['id']}",
        json={"name": "Stationery 2026", "description": "Updated"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Stationery 2026"


def test_duplicate_category_name_rejected(client):
    school_id = _school(client, "DupCat School", "dupcat@test.edu")
    _create_category(client, school_id, "Stationery")
    r = client.post(
        f"{BASE}/categories",
        json={"name": "Stationery"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


# --- Items ---------------------------------------------------------------------
def test_create_list_and_filter_low_stock(client):
    school_id = _school(client, "Items School", "items@test.edu")
    _create_item(client, school_id, "Exercise books", quantity=100.0)
    _create_item(client, school_id, "Whiteboard markers", quantity=5.0, low_stock_threshold=10.0)

    r = client.get(f"{BASE}/items", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert all(i["quantity"] == float(i["quantity"]) for i in r.json())

    r = client.get(f"{BASE}/items?low_stock_only=true", headers={"X-School-Id": school_id})
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "Whiteboard markers"


def test_item_with_category_reports_category_name(client):
    school_id = _school(client, "CatItem School", "catitem@test.edu")
    cat = _create_category(client, school_id, "ICT")
    item = _create_item(client, school_id, "Laptop", category_id=cat["id"])

    r = client.get(f"{BASE}/items/{item['id']}", headers={"X-School-Id": school_id})
    assert r.json()["category_name"] == "ICT"


def test_update_item(client):
    school_id = _school(client, "UpdItem School", "upditem@test.edu")
    item = _create_item(client, school_id, "Pens", quantity=50.0)
    r = client.put(
        f"{BASE}/items/{item['id']}",
        json={"name": "Blue pens", "quantity": 20.0, "unit": "pcs", "unit_cost": 100.0},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Blue pens"


def test_item_with_foreign_category_rejected(client):
    school_id = _school(client, "ForeignCat School", "fcat@test.edu")
    r = client.post(
        f"{BASE}/items",
        json={"name": "Fake", "category_id": str(uuid.uuid4()), "quantity": 1.0},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Stock movements -------------------------------------------------------------
def test_restock_and_issue_update_quantity(client):
    school_id = _school(client, "Stock School", "stock@test.edu")
    item = _create_item(client, school_id, "Chairs", quantity=10.0)

    _adjust_stock(client, school_id, item["id"], 5.0, "restock")
    r = client.get(f"{BASE}/items/{item['id']}", headers={"X-School-Id": school_id})
    assert r.json()["quantity"] == 15.0

    _adjust_stock(client, school_id, item["id"], 3.0, "issue")
    r = client.get(f"{BASE}/items/{item['id']}", headers={"X-School-Id": school_id})
    assert r.json()["quantity"] == 12.0


def test_issue_below_zero_rejected(client):
    school_id = _school(client, "Short School", "short@test.edu")
    item = _create_item(client, school_id, "Tables", quantity=2.0)
    r = client.post(
        f"{BASE}/movements",
        json={"item_id": item["id"], "delta": 5.0, "movement_type": "issue"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert "Insufficient stock" in r.json()["error"]["message"]
    r = client.get(f"{BASE}/items/{item['id']}", headers={"X-School-Id": school_id})
    assert r.json()["quantity"] == 2.0


def test_movement_history_tracked(client):
    school_id = _school(client, "Hist School", "hist@test.edu")
    item = _create_item(client, school_id, "Desks", quantity=4.0)
    _adjust_stock(client, school_id, item["id"], 6.0, "restock")
    _adjust_stock(client, school_id, item["id"], 2.0, "issue")

    r = client.get(f"{BASE}/movements?item_id={item['id']}", headers={"X-School-Id": school_id})
    body = r.json()
    assert len(body) == 2
    deltas = sorted(m["delta"] for m in body)
    assert deltas == [-2.0, 6.0]
    assert {m["movement_type"] for m in body} == {"restock", "issue"}


# --- Tenant isolation -----------------------------------------------------------
def test_cross_school_inventory_isolation(client):
    school_a = _school(client, "IsolInv A", "iinv@test.edu")
    cat = _create_category(client, school_a, "ICT")
    item = _create_item(client, school_a, "Laptop", category_id=cat["id"])

    register_school(client, name="IsolInv B", email="iinvb@test.edu")
    school_b = active_school_id(client)

    r = client.get(f"{BASE}/items/{item['id']}", headers={"X-School-Id": school_b})
    assert r.status_code == 404
    r = client.get(f"{BASE}/categories", headers={"X-School-Id": school_b})
    assert r.json() == []

    r = client.post(
        f"{BASE}/movements",
        json={"item_id": item["id"], "delta": 1.0, "movement_type": "restock"},
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404

    r = client.put(
        f"{BASE}/categories/{cat['id']}",
        json={"name": "Hijacked"},
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404


# --- Permission gate ------------------------------------------------------------
def _teacher_membership(db: Session, school_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == "teacher"))
    assert role is not None
    user = User(
        email="inv-teacher@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Miss I",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_inventory_requires_permission(client, db: Session):
    register_school(client, name="InvPerm School", email="invperm@test.edu")
    school_id = active_school_id(client)
    token, _ = _teacher_membership(db, school_id)  # teacher has no inventory perms

    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/items", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(
        f"{BASE}/items",
        json={"name": "Hack", "quantity": 1.0},
        headers=headers,
    )
    assert r.status_code == 403

    r = client.post(
        f"{BASE}/categories",
        json={"name": "Hack"},
        headers=headers,
    )
    assert r.status_code == 403
