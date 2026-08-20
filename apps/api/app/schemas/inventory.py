"""Inventory schemas: categories, items, and stock movements."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InventoryCategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class InventoryCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime


class InventoryItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    category_id: Optional[uuid.UUID] = None
    sku: Optional[str] = Field(None, max_length=60)
    quantity: float = Field(0, ge=0)
    unit: Optional[str] = Field(None, max_length=30)
    unit_cost: float = Field(0, ge=0)
    low_stock_threshold: float = Field(0, ge=0)
    notes: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(True)


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category_id: Optional[uuid.UUID]
    sku: Optional[str]
    quantity: float
    unit: Optional[str]
    unit_cost: float
    low_stock_threshold: float
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    category_name: Optional[str] = None


class StockMovementIn(BaseModel):
    item_id: uuid.UUID = Field(...)
    delta: float = Field(..., description="Positive = restock, negative = issue")
    movement_type: str = Field(..., pattern="^(restock|issue)$")
    reason: Optional[str] = Field(None, max_length=300)


class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    delta: float
    movement_type: str
    reason: Optional[str]
    performed_by: Optional[uuid.UUID]
    created_at: datetime