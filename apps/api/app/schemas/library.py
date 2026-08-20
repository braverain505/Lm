"""Library schemas: books and borrowings."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BookIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=250)
    author: Optional[str] = Field(None, max_length=200)
    isbn: Optional[str] = Field(None, max_length=32)
    category: Optional[str] = Field(None, max_length=80)
    publisher: Optional[str] = Field(None, max_length=150)
    year: Optional[int] = Field(None, ge=1000, le=3000)
    total_copies: int = Field(1, ge=1, le=10000)
    is_active: bool = Field(True)


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    author: Optional[str]
    isbn: Optional[str]
    category: Optional[str]
    publisher: Optional[str]
    year: Optional[int]
    total_copies: int
    available_copies: int
    is_active: bool
    created_at: datetime


class BorrowingIn(BaseModel):
    book_id: uuid.UUID = Field(...)
    borrower_type: str = Field(..., pattern="^(student|staff)$")
    student_id: Optional[uuid.UUID] = None
    staff_id: Optional[uuid.UUID] = None
    due_on: date = Field(...)
    notes: Optional[str] = Field(None, max_length=2000)


class BorrowingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    borrower_type: str
    student_id: Optional[uuid.UUID]
    staff_id: Optional[uuid.UUID]
    borrowed_on: date
    due_on: date
    returned_on: Optional[date]
    status: str
    notes: Optional[str]
    created_at: datetime
    book_title: Optional[str] = None
    borrower_name: Optional[str] = None


class BorrowingReturnIn(BaseModel):
    returned_on: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)