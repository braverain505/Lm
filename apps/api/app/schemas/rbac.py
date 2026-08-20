"""RBAC schemas: roles and the permission catalog."""
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    domain: str
    description: str | None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_system: bool


class RoleDetail(RoleOut):
    permissions: list[str] = []


class RoleCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_]+$", max_length=64)
    name: str = Field(min_length=2, max_length=120)
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    permissions: list[str] | None = None


class PermissionUpdate(BaseModel):
    permissions: list[str]