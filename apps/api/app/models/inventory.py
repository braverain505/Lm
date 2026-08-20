"""Inventory: item categories, items, and stock movement tracking."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class InventoryCategory(TenantScopedBase, Base):
    """A grouping for inventory items (e.g. Stationery, Furniture, ICT)."""

    __tablename__ = "inventory_categories"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_inventory_category_school_name"),
    )

    def __repr__(self) -> str:
        return f"InventoryCategory(id={self.id}, name={self.name})"


class InventoryItem(TenantScopedBase, Base):
    """A tracked inventory item with current stock and a unit cost."""

    __tablename__ = "inventory_items"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_categories.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    sku: Mapped[str | None] = mapped_column(String(60), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    unit: Mapped[str | None] = mapped_column(String(30))  # pcs, reams, litres...
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    low_stock_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("school_id", "sku", name="uq_inventory_item_school_sku"),
    )

    def __repr__(self) -> str:
        return f"InventoryItem(id={self.id}, name={self.name}, qty={self.quantity})"


class StockMovement(TenantScopedBase, Base):
    """An inbound/outbound stock event that adjusts an item's quantity.

    ``delta`` is signed: positive for restock/in, negative for issue/out.
    Applying a movement mutates ``item.quantity`` so the item stays the
    source of truth and movements are the audit trail.
    """

    __tablename__ = "stock_movements"

    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)  # restock | issue
    reason: Mapped[str | None] = mapped_column(String(300))
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"StockMovement(item={self.item_id}, delta={self.delta}, type={self.movement_type})"


__all__ = ["InventoryCategory", "InventoryItem", "StockMovement"]
