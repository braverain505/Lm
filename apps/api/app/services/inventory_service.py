"""Inventory service layer: categories, items, stock movement tracking."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import InventoryCategory, InventoryItem, StockMovement
from ..schemas.inventory import InventoryCategoryIn, InventoryItemIn


def _two(v: float) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


# --- Categories ----------------------------------------------------------------------
def list_categories(db: Session, school_id: uuid.UUID) -> list[InventoryCategory]:
    return list(
        db.scalars(
            select(InventoryCategory)
            .where(InventoryCategory.school_id == school_id)
            .order_by(InventoryCategory.name)
        )
    )


def create_category(
    db: Session, school_id: uuid.UUID, *, data: InventoryCategoryIn
) -> InventoryCategory:
    existing = db.scalar(
        select(InventoryCategory).where(
            InventoryCategory.school_id == school_id,
            InventoryCategory.name == data.name,
        )
    )
    if existing:
        raise ValidationError("A category with this name already exists")
    cat = InventoryCategory(
        school_id=school_id, name=data.name, description=data.description
    )
    db.add(cat)
    db.flush()
    return cat


def update_category(
    db: Session,
    category_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    data: InventoryCategoryIn,
) -> InventoryCategory:
    cat = db.get(InventoryCategory, category_id)
    if cat is None or cat.school_id != school_id:
        raise NotFoundError("Category not found")
    other = db.scalar(
        select(InventoryCategory).where(
            InventoryCategory.school_id == school_id,
            InventoryCategory.name == data.name,
            InventoryCategory.id != category_id,
        )
    )
    if other:
        raise ValidationError("Another category with this name already exists")
    cat.name = data.name
    cat.description = data.description
    db.flush()
    return cat


# --- Items ---------------------------------------------------------------------------
def _item_with_category(db: Session, school_id: uuid.UUID, item: InventoryItem) -> dict:
    cat_name = None
    if item.category_id:
        cat = db.get(InventoryCategory, item.category_id)
        cat_name = cat.name if cat and cat.school_id == school_id else None
    return {
        "id": item.id,
        "name": item.name,
        "category_id": item.category_id,
        "sku": item.sku,
        "quantity": float(item.quantity),
        "unit": item.unit,
        "unit_cost": float(item.unit_cost),
        "low_stock_threshold": float(item.low_stock_threshold),
        "notes": item.notes,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "category_name": cat_name,
    }


def list_items(db: Session, school_id: uuid.UUID, *, low_stock_only: bool = False) -> list[dict]:
    stmt = select(InventoryItem).where(InventoryItem.school_id == school_id)
    if low_stock_only:
        stmt = stmt.where(InventoryItem.quantity <= InventoryItem.low_stock_threshold)
    stmt = stmt.order_by(InventoryItem.name)
    return [_item_with_category(db, school_id, item) for item in db.scalars(stmt)]


def get_item(db: Session, item_id: uuid.UUID, school_id: uuid.UUID) -> dict:
    item = db.get(InventoryItem, item_id)
    if item is None or item.school_id != school_id:
        raise NotFoundError("Inventory item not found")
    return _item_with_category(db, school_id, item)


def create_item(
    db: Session, school_id: uuid.UUID, *, data: InventoryItemIn
) -> dict:
    if data.category_id:
        cat = db.get(InventoryCategory, data.category_id)
        if cat is None or cat.school_id != school_id:
            raise NotFoundError("Category not found")
    if data.sku:
        existing = db.scalar(
            select(InventoryItem).where(
                InventoryItem.school_id == school_id, InventoryItem.sku == data.sku
            )
        )
        if existing:
            raise ValidationError("An item with this SKU already exists")
    item = InventoryItem(
        school_id=school_id,
        name=data.name,
        category_id=data.category_id,
        sku=data.sku,
        quantity=_two(data.quantity),
        unit=data.unit,
        unit_cost=_two(data.unit_cost),
        low_stock_threshold=_two(data.low_stock_threshold),
        notes=data.notes,
        is_active=data.is_active,
    )
    db.add(item)
    db.flush()
    return _item_with_category(db, school_id, item)


def update_item(
    db: Session, item_id: uuid.UUID, school_id: uuid.UUID, *, data: InventoryItemIn
) -> dict:
    item = db.get(InventoryItem, item_id)
    if item is None or item.school_id != school_id:
        raise NotFoundError("Inventory item not found")
    if data.category_id:
        cat = db.get(InventoryCategory, data.category_id)
        if cat is None or cat.school_id != school_id:
            raise NotFoundError("Category not found")
    if data.sku:
        other = db.scalar(
            select(InventoryItem).where(
                InventoryItem.school_id == school_id,
                InventoryItem.sku == data.sku,
                InventoryItem.id != item_id,
            )
        )
        if other:
            raise ValidationError("Another item with this SKU already exists")
    item.name = data.name
    item.category_id = data.category_id
    item.sku = data.sku
    item.unit = data.unit
    item.unit_cost = _two(data.unit_cost)
    item.low_stock_threshold = _two(data.low_stock_threshold)
    item.notes = data.notes
    item.is_active = data.is_active
    db.flush()
    return _item_with_category(db, school_id, item)


# --- Stock movements -----------------------------------------------------------------
def adjust_stock(
    db: Session,
    school_id: uuid.UUID,
    *,
    item_id: uuid.UUID,
    movement_type: str,
    delta: float,
    reason: str | None,
    performed_by: uuid.UUID,
) -> dict:
    if delta == 0:
        raise ValidationError("Stock movement delta cannot be zero")
    item = db.get(InventoryItem, item_id)
    if item is None or item.school_id != school_id:
        raise NotFoundError("Inventory item not found")

    signed = _two(delta)
    if movement_type == "restock":
        signed = abs(signed)
    elif movement_type == "issue":
        signed = -abs(signed)
    else:
        raise ValidationError("movement_type must be 'restock' or 'issue'")

    new_qty = item.quantity + signed
    if new_qty < 0:
        raise ValidationError(
            f"Insufficient stock: only {float(item.quantity)} {item.unit or 'units'} available"
        )

    item.quantity = new_qty
    db.flush()  # persist the adjusted quantity

    movement = StockMovement(
        school_id=school_id,
        item_id=item.id,
        delta=signed,
        movement_type=movement_type,
        reason=reason,
        performed_by=performed_by,
    )
    db.add(movement)
    db.flush()
    return {
        "id": movement.id,
        "item_id": movement.item_id,
        "delta": float(signed),
        "movement_type": movement.movement_type,
        "reason": movement.reason,
        "performed_by": movement.performed_by,
        "created_at": movement.created_at,
        **{k: v for k, v in _item_with_category(db, school_id, item).items()},
    }


def list_movements(db: Session, school_id: uuid.UUID, item_id: uuid.UUID | None = None) -> list[dict]:
    stmt = (
        select(StockMovement)
        .where(StockMovement.school_id == school_id)
        .order_by(StockMovement.created_at.desc())
    )
    if item_id:
        stmt = stmt.where(StockMovement.item_id == item_id)
    return [
        {
            "id": m.id,
            "item_id": m.item_id,
            "delta": float(m.delta),
            "movement_type": m.movement_type,
            "reason": m.reason,
            "performed_by": m.performed_by,
            "created_at": m.created_at,
        }
        for m in db.scalars(stmt)
    ]