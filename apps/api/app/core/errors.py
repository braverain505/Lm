"""Structured error contract. Every API error is returned as:

    {"error": {"code": "ERR_...", "message": "...", "details": {...?}}}

so clients can branch on machine-readable codes instead of HTTP status alone.
"""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Raised by services/routers for all expected failures."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


# --- Error code catalog -----------------------------------------------------
ERR_UNAUTHENTICATED = "ERR_UNAUTHENTICATED"
ERR_AUTH_FAILED = "ERR_AUTH_FAILED"
ERR_TOKEN_EXPIRED = "ERR_TOKEN_EXPIRED"
ERR_TOKEN_REUSED = "ERR_TOKEN_REUSED"
ERR_ACCOUNT_DISABLED = "ERR_ACCOUNT_DISABLED"
ERR_ACCOUNT_LOCKED = "ERR_ACCOUNT_LOCKED"
ERR_NOT_MEMBER = "ERR_NOT_MEMBER"  # neutral 404 — do not leak school existence
ERR_PERMISSION_DENIED = "ERR_PERMISSION_DENIED"
ERR_MEMBERSHIP_SUSPENDED = "ERR_MEMBERSHIP_SUSPENDED"
ERR_IMPERSONATION_ACTIVE = "ERR_IMPERSONATION_ACTIVE"
ERR_NOT_FOUND = "ERR_NOT_FOUND"
ERR_DUPLICATE = "ERR_DUPLICATE"
ERR_VALIDATION = "ERR_VALIDATION"
ERR_CONFLICT = "ERR_CONFLICT"
ERR_SCORE_OVER_MAX = "ERR_SCORE_OVER_MAX"
ERR_SCORE_NEGATIVE = "ERR_SCORE_NEGATIVE"
ERR_RESULT_LOCKED = "ERR_RESULT_LOCKED"
ERR_WEIGHT_SUM = "ERR_WEIGHT_SUM"
ERR_RATE_LIMITED = "ERR_RATE_LIMITED"
ERR_FEATURE_DISABLED = "ERR_FEATURE_DISABLED"
ERR_ASSIGNMENT = "ERR_ASSIGNMENT"  # 403: actor not assigned to this arm/subject
ERR_AI_NOT_CONFIGURED = "ERR_AI_NOT_CONFIGURED"  # 503: provider key missing
ERR_PREMIUM_REQUIRED = "ERR_PREMIUM_REQUIRED"  # 403: AI features are a paid add-on
ERR_SCHOOL_SUSPENDED = "ERR_SCHOOL_SUSPENDED"  # 403: school disabled by the Lumo admin
ERR_PIN_INVALID = "ERR_PIN_INVALID"  # 404: neutral — admission no / PIN mismatch


class ValidationError(APIError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(422, ERR_VALIDATION, message, details)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(404, ERR_NOT_FOUND, message)


class ConflictError(APIError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(409, ERR_CONFLICT, message, details)


class PermissionDeniedError(APIError):
    def __init__(self, message: str = "You do not have permission to do that") -> None:
        super().__init__(403, ERR_PERMISSION_DENIED, message)


class NotMemberError(APIError):
    """Neutral response for a request against a school the caller is not in."""

    def __init__(self) -> None:
        super().__init__(404, ERR_NOT_MEMBER, "School not found")


class PremiumRequiredError(APIError):
    """The school has not subscribed to the premium (AI) feature plan."""

    def __init__(self, message: str = "This is a premium feature. Kindly subscribe.") -> None:
        super().__init__(403, ERR_PREMIUM_REQUIRED, message)


class SchoolSuspendedError(APIError):
    """The school has been disabled by the Lumo platform admin."""

    def __init__(self, message: str = "This school has been disabled. Contact Lumo support.") -> None:
        super().__init__(403, ERR_SCHOOL_SUSPENDED, message)


def _envelope(code: str, message: str, details: dict[str, Any] | None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, Any] = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            errors[loc or "_"] = err.get("msg")
        return JSONResponse(
            status_code=422,
            content=_envelope(ERR_VALIDATION, "Invalid request payload", errors),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        # Never leak internals; log and return a generic message.
        import logging

        logging.getLogger(__name__).exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("ERR_INTERNAL", "An unexpected error occurred", None),
        )