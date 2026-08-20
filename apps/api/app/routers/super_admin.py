"""SchoolOS Super Admin endpoints: the platform owner's command center.

Every route is guarded by ``require_platform_admin`` (``User.is_superadmin``) —
no school context is involved. This is intentionally separate from the school
dashboards; the frontend mounts it under ``/super-admin``.
"""
import uuid

from fastapi import APIRouter, Depends, Request

from ..core.deps import DbSession, require_platform_admin
from ..schemas.super_admin import (
    AnnouncementCreateRequest,
    SchoolCreateRequest,
    SettingsUpdateRequest,
    SubscriptionUpdateRequest,
    TicketCreateRequest,
    TicketUpdateRequest,
)
from ..services import super_admin_service
from ..models.identity import User

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def _client_info(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    label = (ua or "unknown")[:120]
    return label, ip


PlatformAdmin = Depends(require_platform_admin)


# --- Overview / analytics ---------------------------------------------------

@router.get("/overview")
def overview(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.overview(db)


@router.get("/growth")
def growth(
    db: DbSession,
    range: str = "12m",
    _admin: User = PlatformAdmin,
):
    return super_admin_service.growth(db, range)


@router.get("/revenue")
def revenue(
    db: DbSession,
    range: str = "12m",
    plan: str | None = None,
    source: str | None = None,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.revenue(db, range, plan, source)


@router.get("/subscriptions")
def subscriptions(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.subscriptions(db)


@router.get("/ai")
def ai_analytics(
    db: DbSession,
    range: str = "12m",
    feature: str | None = None,
    plan: str | None = None,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.ai_overview(db, range, feature, plan)


@router.get("/users")
def users_analytics(
    db: DbSession,
    range: str = "12m",
    _admin: User = PlatformAdmin,
):
    return super_admin_service.users_analytics(db, range)


@router.get("/engagement")
def engagement(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.engagement(db)


@router.get("/geo")
def geo(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.geo(db)


@router.get("/activity")
def activity(
    db: DbSession,
    limit: int = 30,
    category: str | None = None,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.activity(db, limit, category)


@router.get("/health")
def health(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.health(db)


# --- Schools ----------------------------------------------------------------

@router.get("/schools")
def list_schools(
    db: DbSession,
    q: str | None = None,
    status: str | None = None,
    plan: str | None = None,
    state: str | None = None,
    sort: str = "created_desc",
    page: int = 1,
    per_page: int = 20,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.list_schools(
        db,
        q=q,
        status=status,
        plan=plan,
        state=state,
        sort=sort,
        page=page,
        per_page=per_page,
    )


@router.get("/schools/{school_id}")
def school_detail(
    school_id: uuid.UUID,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.school_detail(db, school_id)


@router.post("/schools", status_code=201)
def add_school(
    payload: SchoolCreateRequest,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.add_school(
        db,
        name=payload.name.strip(),
        school_type=payload.school_type,
        state=payload.state,
        country=payload.country,
        admin_full_name=payload.admin_full_name.strip(),
        admin_email=payload.admin_email.strip().lower(),
        plan_code=payload.plan_code,
        actor_id=_admin.id,
        ip=ip,
    )
    db.commit()
    return result


@router.patch("/schools/{school_id}/subscription")
def update_subscription(
    school_id: uuid.UUID,
    payload: SubscriptionUpdateRequest,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.update_subscription(
        db,
        school_id,
        plan_code=payload.plan_code,
        status=payload.status,
        ai_credits_total=payload.ai_credits_total,
        ends_at=payload.ends_at,
        actor_id=_admin.id,
        ip=ip,
    )
    db.commit()
    return result


@router.post("/schools/{school_id}/reset-admin")
def reset_admin(
    school_id: uuid.UUID,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.reset_admin(
        db, school_id, actor_id=_admin.id, ip=ip
    )
    db.commit()
    return result


@router.post("/schools/{school_id}/impersonate")
def impersonate(
    school_id: uuid.UUID,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.impersonate(
        db, school_id, platform_user=_admin, ip=ip
    )
    db.commit()
    return result


# --- Support ----------------------------------------------------------------

@router.get("/issues")
def issues(
    db: DbSession,
    severity: str | None = None,
    status: str | None = None,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.issues(db, severity, status)


@router.get("/tickets")
def tickets(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.tickets(db)


@router.post("/tickets", status_code=201)
def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.create_ticket(
        db,
        school_id=payload.school_id,
        subject=payload.subject.strip(),
        description=payload.description,
        category=payload.category,
        severity=payload.severity,
        created_by=_admin.id,
        ip=ip,
    )
    db.commit()
    return result


@router.patch("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdateRequest,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    result = super_admin_service.update_ticket(
        db,
        ticket_id,
        status=payload.status,
        resolution_note=payload.resolution_note,
        actor_id=_admin.id,
    )
    db.commit()
    return result


# --- Alerts / notifications -------------------------------------------------

@router.get("/notifications")
def notifications(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service._notifications(db)


@router.post("/notifications/read")
def mark_notifications_read(
    ids: list[str],
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    super_admin_service.mark_notifications_read(db, ids)
    db.commit()
    return {"ok": True}


# --- Audit trail ------------------------------------------------------------

@router.get("/audit")
def audit(
    db: DbSession,
    q: str | None = None,
    action: str | None = None,
    entity: str | None = None,
    page: int = 1,
    per_page: int = 30,
    _admin: User = PlatformAdmin,
):
    return super_admin_service.audit(
        db,
        q=q,
        action=action,
        entity=entity,
        page=page,
        per_page=per_page,
    )


# --- Platform configuration -------------------------------------------------

@router.get("/settings")
def platform_settings(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.platform_settings(db)


@router.patch("/settings")
def update_platform_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.update_platform_settings(
        db, payload.updates, actor_id=_admin.id, ip=ip
    )
    db.commit()
    return result


@router.get("/announcements")
def announcements(db: DbSession, _admin: User = PlatformAdmin):
    return super_admin_service.announcements(db)


@router.post("/announcements", status_code=201)
def create_announcement(
    payload: AnnouncementCreateRequest,
    request: Request,
    db: DbSession,
    _admin: User = PlatformAdmin,
):
    _, ip = _client_info(request)
    result = super_admin_service.create_announcement(
        db,
        title=payload.title.strip(),
        body=payload.body.strip(),
        audience=payload.audience,
        severity=payload.severity,
        created_by=_admin.id,
        ip=ip,
    )
    db.commit()
    return result