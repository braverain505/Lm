"""RBAC endpoints: roles CRUD + permission catalog, school-scoped."""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import ActiveSchool, DbSession, require_permission
from ..core.permissions import ROLES_MANAGE
from ..schemas.rbac import (
    PermissionOut,
    RoleCreate,
    RoleDetail,
    RoleUpdate,
)
from ..services import rbac_service

router = APIRouter(prefix="/roles", tags=["roles"])


def _detail(db: DbSession, role) -> RoleDetail:
    perms = rbac_service.permissions_for_role(db, role.id)
    return RoleDetail(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=perms,
    )


# NOTE: declared before /{role_id} so FastAPI matches the literal path first.
@router.get("/permissions/catalog", response_model=list[PermissionOut])
def permission_catalog(ctx: ActiveSchool, db: DbSession):
    perms = rbac_service.list_permission_catalog(db)
    return [PermissionOut.model_validate(p) for p in perms]


@router.get("", response_model=list[RoleDetail])
def list_roles(ctx: ActiveSchool, db: DbSession):
    roles = rbac_service.list_roles(db, ctx.school.id)
    return [_detail(db, r) for r in roles]


@router.post("", response_model=RoleDetail, status_code=201)
def create_role(
    payload: RoleCreate,
    db: DbSession,
    ctx=Depends(require_permission(ROLES_MANAGE)),
):
    role = rbac_service.create_role(
        db, ctx.school.id, code=payload.code, name=payload.name,
        permissions=payload.permissions,
    )
    db.commit()
    return _detail(db, role)


@router.get("/{role_id}", response_model=RoleDetail)
def get_role(role_id: uuid.UUID, ctx: ActiveSchool, db: DbSession):
    role = rbac_service.get_role(db, ctx.school.id, role_id)
    return _detail(db, role)


@router.patch("/{role_id}", response_model=RoleDetail)
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: DbSession,
    ctx=Depends(require_permission(ROLES_MANAGE)),
):
    role = rbac_service.update_role(
        db, ctx.school.id, role_id,
        name=payload.name, permissions=payload.permissions,
    )
    db.commit()
    return _detail(db, role)


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ROLES_MANAGE)),
):
    rbac_service.delete_role(db, ctx.school.id, role_id)
    db.commit()