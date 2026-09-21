"""Application settings — loaded from environment / .env (pydantic-settings)."""
import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Dev convenience only: localhost. Any hosted frontend must set CORS_ORIGINS
# explicitly — the API no longer ships other sites' origins as a silent default.
_DEFAULT_CORS = [
    "http://localhost:3000",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Application ---
    app_name: str = "Clearis API"
    debug: bool = False
    api_base_path: str = "/api"
    cors_origins: list[str] = _DEFAULT_CORS
    # Public origin of the web app. Used to build links that go back to the
    # browser (password-reset links, welcome-email sign-in button).
    web_base_url: str = "http://localhost:3000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Handle CORS_ORIGINS env var that might be a JSON string,
        a comma-separated string, or empty/invalid."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return _DEFAULT_CORS
            # Try JSON parse first (e.g. ["https://example.com"])
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # Fall back to comma-separated
            return [o.strip() for o in v.split(",") if o.strip()]
        return _DEFAULT_CORS

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg2://clearis:clearis@localhost:5432/clearis_dev"
    )

    # --- Security ---
    jwt_secret: str = "CHANGE_ME_dev_only_secret"  # set a strong secret in .env
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_name: str = "clearis_session"
    cookie_secure: bool = False  # True behind TLS
    # Cookies default to Lax: the web app talks to the API same-origin through
    # its /api/proxy rewrite, so cross-site sending (SameSite=None, which
    # widens CSRF exposure) is never needed implicitly. A deployment that
    # really does call the API cross-site from a browser may set
    # COOKIE_SAMESITE=none — validation below then also requires COOKIE_SECURE.
    cookie_samesite: str = "lax"
    impersonation_cookie: str = "clearis_impersonation"
    cookie_domain: str | None = None

    # --- Auth behavior ---
    # When True (dev), password-reset links are returned by the API instead of emailed.
    dev_email: bool = True
    allow_email_verification_skip: bool = True

    # --- Infra ---
    use_redis: bool = False  # Phase 2: background jobs move to Celery+Redis
    storage_driver: str = "local"  # local | s3 (s3 later)
    storage_base_dir: str = ".storage"

    # --- Email (transactional) ---
    # Two transports. "auto" (the default) prefers SMTP when it is fully
    # configured and otherwise uses Resend, so an existing deployment that only
    # set RESEND_API_KEY carries on unchanged. Pin one explicitly when both are
    # filled in — otherwise a leftover SMTP account silently wins.
    email_transport: str = "auto"  # auto | smtp | resend

    # SMTP — how the platform's own mail leaves, from the Clearis inbox. With
    # Gmail this is smtp.gmail.com:587 and a 16-character App Password: Google
    # rejects a normal account password, and an App Password requires 2-Step
    # Verification on the account first.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # display name + address; defaults to SMTP_USER
    smtp_starttls: bool = True
    smtp_timeout_seconds: float = 20.0

    # Resend API key, for deployments with a verified sending domain. When no
    # transport is configured, sending is skipped in development (the email is
    # logged instead) and refused with a clear error in production — receipts
    # must never be silently "sent".
    resend_api_key: str = ""
    email_from: str = "Clearis <no-reply@clearis.app>"
    email_reply_to: str = ""
    email_timeout_seconds: float = 20.0

    # Where the internal "a new school registered" notice goes. Empty disables
    # it; it is never sent to the school itself.
    owner_alert_email: str = "clearisinfo@gmail.com"

    # --- LLM (Groq) ---
    # When GROQ_API_KEY is unset the AI engines keep working with their
    # deterministic template fallbacks (no external calls, cost $0).
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 60.0

    # --- Seeding ---
    seed_demo_school: bool = True

    @field_validator("web_base_url")
    @classmethod
    def _strip_web_base_slash(cls, v: str) -> str:
        """Normalise so link building never produces a doubled slash."""
        return v.strip().rstrip("/")

    @field_validator("cookie_samesite")
    @classmethod
    def _samesite_value(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("lax", "strict", "none"):
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return v

    @field_validator("email_transport")
    @classmethod
    def _email_transport_value(cls, v: str) -> str:
        v = (v or "auto").strip().lower()
        if v not in ("auto", "smtp", "resend"):
            raise ValueError("EMAIL_TRANSPORT must be one of: auto, smtp, resend")
        return v

    def validate_production_config(self) -> None:
        """Validate that critical settings are production-ready.

        Raises ValueError if production requirements are not met. DEBUG alone
        cannot skip the checks any more: a deployment that sets
        COOKIE_SECURE=true is declaring itself a (TLS-served) production
        instance and must pass validation even if DEBUG was left on.
        """
        # SameSite=None without Secure is rejected outright by every modern
        # browser — reject the misconfiguration regardless of environment.
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError(
                "COOKIE_SAMESITE=none requires COOKIE_SECURE=true"
            )

        if self.debug and not self.cookie_secure:
            # Local development (plain http, cookies not marked Secure).
            return

        errors = []

        # JWT secret must be strong (min 32 bytes for HS256)
        if len(self.jwt_secret.encode()) < 32:
            errors.append(
                f"JWT_SECRET must be at least 32 bytes (current: {len(self.jwt_secret.encode())} bytes). "
                "Generate with: openssl rand -hex 32"
            )

        # Common weak secrets
        weak_secrets = ["CHANGE_ME", "dev_only", "secret", "password", "test"]
        if any(weak in self.jwt_secret.lower() for weak in weak_secrets):
            errors.append(
                "JWT_SECRET appears to be a default/weak value. "
                "Generate with: openssl rand -hex 32"
            )

        # Cookie security
        if not self.cookie_secure:
            errors.append(
                "COOKIE_SECURE must be true in production (requires HTTPS)"
            )

        # Development email mode
        if self.dev_email:
            errors.append(
                "DEV_EMAIL must be false in production "
                "(password reset links should be emailed, not returned in API responses)"
            )

        if errors:
            error_msg = "Production configuration validation failed:\n" + "\n".join(
                f"  - {err}" for err in errors
            )
            raise ValueError(error_msg)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()