"""Lesson-plan schemas: deterministic AI lesson plans (Phase 2 slice 5)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LessonPlanCreate(BaseModel):
    term_id: uuid.UUID
    subject_id: uuid.UUID
    class_arm_id: uuid.UUID
    topic: str = Field(min_length=1, max_length=200)
    periods: int = Field(default=2, ge=1, le=10)


class LessonPlanOut(BaseModel):
    """A stored plan for one subject × class × term × topic cell. The
    structured ``plan`` dict is fully ground in the school's own data."""

    id: uuid.UUID
    term_id: uuid.UUID
    subject_id: uuid.UUID
    class_arm_id: uuid.UUID
    topic: str
    plan: dict
    provider: str
    model: str | None
    revision: int
    generated_at: datetime