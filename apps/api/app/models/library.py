"""Library: book catalogue and borrowing/return tracking."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class Book(TenantScopedBase, Base):
    """A catalogue entry for a library resource."""

    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200))
    isbn: Mapped[str | None] = mapped_column(String(32), index=True)
    category: Mapped[str | None] = mapped_column(String(80))
    publisher: Mapped[str | None] = mapped_column(String(150))
    year: Mapped[int | None] = mapped_column(Integer)
    total_copies: Mapped[int] = mapped_column(Integer, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(default=True)

    def __repr__(self) -> str:
        return f"Book(id={self.id}, title={self.title})"


class Borrowing(TenantScopedBase, Base):
    """A checkout of one copy of a book by a student or staff member."""

    __tablename__ = "borrowings"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    borrower_type: Mapped[str] = mapped_column(String(16), nullable=False)  # student | staff
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), index=True, nullable=True
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"), index=True, nullable=True
    )
    borrowed_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    returned_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="borrowed")  # borrowed | returned
    notes: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"Borrowing(id={self.id}, book={self.book_id}, status={self.status})"


__all__ = ["Book", "Borrowing"]
