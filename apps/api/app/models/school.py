"""School (tenant) and campus models."""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPkMixin, utcnow
from .enums import SchoolType


class School(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(40))
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    school_type: Mapped[SchoolType] = mapped_column(
        String(24), default=SchoolType.PRIMARY.value, nullable=False
    )
    established_year: Mapped[int | None]
    website: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(60), default="Africa/Lagos")
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    logo_url: Mapped[str | None] = mapped_column(String(500))
    state: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2), default="NG")
    # Per-school configuration: result title format, grading defaults,
    # assessment structure, feature toggles (never PII).
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    campuses: Mapped[list["Campus"]] = relationship(
        back_populates="school", cascade="all, delete-orphan"
    )

    @property
    def display_name(self) -> str:
        return self.short_name or self.name


class Campus(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "campuses"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_campus_name"),)

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    school: Mapped[School] = relationship(back_populates="campuses")


# Re-export for alembic autogenerate import hygiene.
__all__ = ["School", "Campus"]