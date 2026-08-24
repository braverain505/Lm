"""Auth: registration, login, refresh, password reset, /me contracts."""
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterSchoolRequest(BaseModel):
    school_name: str = Field(min_length=2, max_length=160)
    school_type: str = Field(default="primary", max_length=24)
    established_year: int | None = Field(default=None, ge=1800, le=2100)
    website: str | None = Field(default=None, max_length=200)
    school_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    state: str | None = Field(default=None, max_length=120)
    country: str = Field(default="NG", min_length=2, max_length=2)
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserSummary"


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    status: str
    is_superadmin: bool = False


class MembershipOut(BaseModel):
    membership_id: uuid.UUID
    school_id: uuid.UUID
    school_name: str
    school_slug: str
    status: str
    role: dict | None
    permissions: list[str]
    ai_enabled: bool = False
    suspended: bool = False


class MeResponse(BaseModel):
    user: UserSummary
    memberships: list[MembershipOut]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetResponse(BaseModel):
    message: str
    reset_token: str | None = None  # dev only


class RefreshRequest(BaseModel):
    refresh_token: str


class ImpersonateEnterRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangeEmailRequest(BaseModel):
    current_password: str
    new_email: EmailStr


TokenResponse.model_rebuild()