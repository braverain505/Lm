"""Authentication endpoints. Sets httpOnly cookies for the web app; also accepts
bearer tokens for API clients. The refresh token cookie powers rotation + logout
without ever exposing either token to JavaScript."""
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from ..config import settings
from ..core import security
from ..core.deps import AnyUser, DbSession, require_platform_admin
from ..core.rate_limit import limiter
from ..schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ImpersonateEnterRequest,
    LoginRequest,
    MeResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
    RefreshRequest,
    RegisterSchoolRequest,
    TokenResponse,
    UserSummary,
)
from ..services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "schoolos_refresh"


def _set_cookies(response: Response, result: auth_service.AuthResult) -> None:
    response.set_cookie(
        settings.cookie_name,
        result.access_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        result.refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.refresh_token_days * 86400,
        path="/api/auth",
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    response.delete_cookie(settings.impersonation_cookie, path="/")


def _client_info(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    label = (ua or "unknown")[:120]
    return label, ip


@router.post("/register-school", response_model=TokenResponse, status_code=201)
@limiter.limit("3/hour")  # Prevent registration spam
def register_school(
    payload: RegisterSchoolRequest,
    response: Response,
    request: Request,
    db: DbSession,
):
    device, ip = _client_info(request)
    result = auth_service.register_school(
        db,
        school_name=payload.school_name,
        school_type=payload.school_type,
        admin_email=payload.admin_email,
        admin_full_name=payload.admin_full_name,
        password=payload.password,
        device=device,
        ip=ip,
    )
    db.commit()
    _set_cookies(response, result)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=UserSummary.model_validate(result.user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")  # Prevent brute force attacks
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: DbSession,
):
    device, ip = _client_info(request)
    result = auth_service.login(
        db, email=payload.email, password=payload.password, device=device, ip=ip
    )
    db.commit()
    _set_cookies(response, result)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=UserSummary.model_validate(result.user),
    )


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession):
    raw = request.cookies.get(REFRESH_COOKIE)
    auth_service.logout(db, raw)
    db.commit()
    _clear_cookies(response)
    return {"message": "Signed out"}


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: DbSession, payload: RefreshRequest | None = None):
    raw = request.cookies.get(REFRESH_COOKIE) or (
        payload.refresh_token if payload else None
    )
    if not raw:
        from ..core.errors import APIError, ERR_UNAUTHENTICATED

        raise APIError(401, ERR_UNAUTHENTICATED, "Missing refresh token")
    device, ip = _client_info(request)
    result = auth_service.refresh_session(db, raw, device=device, ip=ip)
    db.commit()
    _set_cookies(response, result)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=UserSummary.model_validate(result.user),
    )


@router.get("/me", response_model=MeResponse)
def me(user: AnyUser, db: DbSession):
    memberships = auth_service.user_memberships(db, user.id)
    return MeResponse(
        user=UserSummary.model_validate(user),
        memberships=memberships,
    )


@router.post("/passwords/reset", response_model=PasswordResetResponse)
@limiter.limit("3/hour")  # Prevent password reset abuse
def request_reset(payload: PasswordResetRequest, request: Request, db: DbSession):
    raw = auth_service.request_password_reset(db, payload.email)
    db.commit()
    return PasswordResetResponse(
        message="If that email exists, a reset link has been sent",
        reset_token=raw if settings.dev_email else None,
    )


@router.post("/passwords/reset/confirm")
def confirm_reset(payload: PasswordResetConfirm, db: DbSession):
    auth_service.confirm_password_reset(db, payload.token, payload.new_password)
    db.commit()
    return {"message": "Password updated"}


@router.post("/impersonate/enter")
def impersonate_enter(
    payload: ImpersonateEnterRequest,
    response: Response,
    request: Request,
    db: DbSession,
    admin=Depends(require_platform_admin),
):
    """Activate a support impersonation session created by the platform admin.

    Only platform admins may enter. Sets the impersonation cookie; from here the
    session resolves to the impersonated school admin (see core/deps.py).
    """
    device, ip = _client_info(request)
    result = auth_service.enter_impersonation(
        db, token=payload.token, platform_user=admin, ip=ip
    )
    db.commit()
    response.set_cookie(
        settings.impersonation_cookie,
        payload.token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=30 * 60,
        path="/",
    )
    return result


@router.post("/impersonate/exit")
def impersonate_exit(
    response: Response,
    request: Request,
    db: DbSession,
    user: AnyUser,
):
    """Leave impersonation. Deliberately NOT platform-admin-gated so a stale
    impersonation cookie can always be cleared."""
    raw = request.cookies.get(settings.impersonation_cookie)
    _, ip = _client_info(request)
    auth_service.exit_impersonation(db, token=raw, platform_user=user, ip=ip)
    db.commit()
    response.delete_cookie(settings.impersonation_cookie, path="/")
    return {"ok": True}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: DbSession,
    user: AnyUser,
):
    """Update the signed-in user's password (used from school settings)."""
    auth_service.change_password(
        db,
        user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        current_refresh_raw=request.cookies.get(REFRESH_COOKIE),
    )
    db.commit()
    return {"message": "Password updated"}


@router.post("/change-email")
def change_email(
    payload: ChangeEmailRequest,
    request: Request,
    db: DbSession,
    user: AnyUser,
):
    """Update the signed-in user's email (used from school settings)."""
    auth_service.change_email(
        db,
        user,
        current_password=payload.current_password,
        new_email=payload.new_email,
        current_refresh_raw=request.cookies.get(REFRESH_COOKIE),
    )
    db.commit()
    return {"message": "Email updated", "email": payload.new_email}