"""Auth: registration, login, refresh, password reset, /me contracts."""
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterSchoolRequest(BaseModel):
    school_name: str = Field(min_length=2, max_length=160)
    school_type: str = Field(default="primary", max_length=24)
    established_year: int | None = Field(default=None, ge=1800, le=2100)
    website: str | None = Field(default=None, max_length=200)
    # Both are compulsory at signup: they are the school's contact details on
    # file, so a workspace can never be created without a way to reach it.
    school_email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    state: str | None = Field(default=None, max_length=120)
    country: str = Field(default="NG", min_length=2, max_length=2)
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Sign in with either an email or a username.

    ``identifier`` is the current field; ``email`` is still accepted so older
    app builds (which post ``email``) keep working. One of the two is required.
    """

    identifier: str | None = Field(default=None, max_length=254)
    email: str | None = Field(default=None, max_length=254)
    password: str

    @model_validator(mode="after")
    def _need_identifier(self):
        if not (self.identifier or self.email):
            raise ValueError("Enter your email or username")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserSummary"


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str | None = None
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