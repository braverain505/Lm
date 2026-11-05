"""Clearis Super Admin schemas: platform-level command center request/response
shapes. Responses are largely passthrough dicts from ``super_admin_service`` so
only request bodies are strictly typed here."""
import uuid

from pydantic import BaseModel, Field


class SchoolCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    school_type: str = Field(default="secondary")
    state: str | None = None
    country: str = "NG"
    admin_full_name: str = Field(min_length=2)
    admin_email: str = Field(min_length=3)
    plan_code: str | None = None


class SubscriptionUpdateRequest(BaseModel):
    plan_code: str | None = None
    status: str | None = None
    ai_credits_total: float | None = None
    ends_at: str | None = None


class TicketCreateRequest(BaseModel):
    school_id: uuid.UUID | None = None
    subject: str = Field(min_length=2)
    description: str | None = None
    category: str = "general"
    severity: str = "low"


class TicketUpdateRequest(BaseModel):
    status: str | None = None
    resolution_note: str | None = None


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=2)
    body: str = Field(min_length=2)
    audience: str = "all"
    severity: str = "info"


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, object] = Field(default_factory=dict)


class BulkStudentRow(BaseModel):
    """One pasted child: a full name plus the class they belong in."""

    full_name: str = Field(min_length=2, max_length=160)
    class_arm_id: uuid.UUID
    gender: str | None = Field(default=None, max_length=16)
    admission_no: str | None = Field(default=None, max_length=40)


class ClassCreateRequest(BaseModel):
    """Create one class for a school while adding students in bulk.

    The session is resolved from ``session_id``, else from an existing session
    named ``session_name``, else the school's current session. When
    ``session_name`` names a session the school does not have yet, it is
    created.
    """

    name: str = Field(min_length=1, max_length=40)
    session_id: uuid.UUID | None = None
    session_name: str | None = Field(default=None, max_length=80)
    # Classes sharing this are ranked as one class group in results ("SS 1"
    # over its Science/Arts/Commercial arms). Only affects results.
    group_name: str | None = Field(default=None, max_length=40)


class BulkStudentCreateRequest(BaseModel):
    """Add many students to one school in a single request.

    ``session_id`` is optional: when omitted the school's current academic
    session is used. Every row's class must belong to that session.
    """

    session_id: uuid.UUID | None = None
    rows: list[BulkStudentRow] = Field(min_length=1, max_length=1000)