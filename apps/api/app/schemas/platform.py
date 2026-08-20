"""Lumo platform administration schemas (global admin dashboard)."""
from datetime import datetime

from pydantic import BaseModel

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