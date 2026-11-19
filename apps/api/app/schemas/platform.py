"""Clearis platform administration schemas (global admin dashboard)."""
from datetime import datetime

from pydantic import BaseModel, Field

import uuid


class SchoolAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None
    slug: str
    school_type: str
    email: str | None
    phone: str | None
    created_at: datetime
    students: int
    class_arms: int
    ai_enabled: bool
    progress_enabled: bool = False
    suspended: bool


class SchoolAiUpdate(BaseModel):
    enabled: bool


class SchoolSuspendedUpdate(BaseModel):
    suspended: bool


class SchoolAdminCreate(BaseModel):
    full_name: str
    email: str
    password: str | None = None


class SchoolAdminCreated(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    school_id: uuid.UUID
    school_name: str
    role_code: str
    password: str | None = None


class TeacherOut(BaseModel):
    school_id: uuid.UUID
    school_name: str
    user_id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    role_code: str
    status: str
    created_at: datetime


class UnpublishResultsIn(BaseModel):
    term_id: uuid.UUID
    # The reason is required: it lands on every affected result row's journal and
    # in the archive, so the platform can answer for the decision later.
    reason: str = Field(min_length=10, max_length=500)


class PublishedTermOut(BaseModel):
    term_id: uuid.UUID
    term_name: str
    term_status: str
    session_id: uuid.UUID
    session_name: str = ""
    counts: dict[str, int]
    published: int
    archive_version: int | None = None
