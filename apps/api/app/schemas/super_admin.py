"""SchoolOS Super Admin schemas: platform-level command center request/response
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