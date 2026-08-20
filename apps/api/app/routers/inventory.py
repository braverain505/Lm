"""Inventory API endpoints: categories, items, and stock movements."""

import uuid

from fastapi import APIRouter, Depends, Query

from ..core.deps import DbSession, require_permission
from ..core.permissions import INVENTORY_VIEW, INVENTORY_MANAGE
from ..schemas.inventory import (
    InventoryCategoryIn,
    InventoryCategoryOut,
    InventoryItemIn,
    InventoryItemOut,
    StockMovementIn,
    StockMovementOut,
)
from ..services.inventory_service import (
    adjust_stock,
    create_category,
    create_item,
    get_item,
    list_categories,
    list_items,
    list_movements,
    update_category,
    update_item,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])


# ──────────────────────────────────────────────────────────────────────
# Categories
# ──────────────────────────────────────────────────────────────────────


@router.get("/categories", response_model=list[InventoryCategoryOut])
def list_categories_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_VIEW)),
):
    return [InventoryCategoryOut.model_validate(c) for c in list_categories(db, ctx.school.id)]


@router.post("/categories", response_model=InventoryCategoryOut, status_code=201)
def create_category_endpoint(
    payload: InventoryCategoryIn,
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_MANAGE)),
):
    result = create_category(db, ctx.school.id, data=payload)
    db.commit()
    return InventoryCategoryOut.model_validate(result)


@router.put("/categories/{category_id}", response_model=InventoryCategoryOut)
def update_category_endpoint(
    category_id: uuid.UUID,
    payload: InventoryCategoryIn,
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_MANAGE)),
):
    result = update_category(db, category_id, ctx.school.id, data=payload)
    db.commit()
    return InventoryCategoryOut.model_validate(result)


# ──────────────────────────────────────────────────────────────────────
# Items
# ──────────────────────────────────────────────────────────────────────


@router.get("/items", response_model=list[InventoryItemOut])
def list_items_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_VIEW)),
    low_stock_only: bool = Query(False),
):
    return list_items(db, ctx.school.id, low_stock_only=low_stock_only)


@router.post("/items", response_model=InventoryItemOut, status_code=201)
def create_item_endpoint(
    payload: InventoryItemIn,
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_MANAGE)),
):
    result = create_item(db, ctx.school.id, data=payload)
    db.commit()
    return result


@router.get("/items/{item_id}", response_model=InventoryItemOut)
def get_item_endpoint(
    item_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_VIEW)),
):
    return get_item(db, item_id, ctx.school.id)


@router.put("/items/{item_id}", response_model=InventoryItemOut)
def update_item_endpoint(
    item_id: uuid.UUID,
    payload: InventoryItemIn,
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_MANAGE)),
):
    result = update_item(db, item_id, ctx.school.id, data=payload)
    db.commit()
    return result


# ──────────────────────────────────────────────────────────────────────
# Stock movements
# ──────────────────────────────────────────────────────────────────────


@router.post("/movements", response_model=StockMovementOut, status_code=201)
def record_movement_endpoint(
    payload: StockMovementIn,
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_MANAGE)),
):
    result = adjust_stock(
        db,
        ctx.school.id,
        item_id=payload.item_id,
        movement_type=payload.movement_type,
        delta=payload.delta,
        reason=payload.reason,
        performed_by=ctx.user.id,
    )
    db.commit()
    return StockMovementOut.model_validate(result)


@router.get("/movements", response_model=list[StockMovementOut])
def list_movements_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(INVENTORY_VIEW)),
    item_id: uuid.UUID | None = Query(None),
):
    return list_movements(db, ctx.school.id, item_id=item_id)