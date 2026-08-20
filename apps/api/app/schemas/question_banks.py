"""Question-bank schemas: deterministic AI practice questions (Phase 2 slice 6)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QuestionBankCreate(BaseModel):
    term_id: uuid.UUID
    subject_id: uuid.UUID
    class_arm_id: uuid.UUID
    topic: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, ge=1, le=10)


class QuestionBankOut(BaseModel):
    """A stored bank for one subject × class × term × topic cell. The
    structured ``bank`` dict is fully grounded in the school's own data."""

    id: uuid.UUID
    term_id: uuid.UUID
    subject_id: uuid.UUID
    class_arm_id: uuid.UUID
    topic: str
    bank: dict
    provider: str
    model: str | None
    revision: int
    generated_at: datetime