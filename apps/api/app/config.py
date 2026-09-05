"""Application settings — loaded from environment / .env (pydantic-settings)."""
import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_CORS = [
    "http://localhost:3000",
    "https://demolumo.vercel.app",
    "https://clearis.site",
    "https://www.clearis.site",
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
        "postgresql+psycopg2://schoolos:schoolos@localhost:5432/schoolos_dev"
    )

    # --- Security ---
    jwt_secret: str = "CHANGE_ME_dev_only_secret"  # set a strong secret in .env
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_name: str = "schoolos_session"
    cookie_secure: bool = False  # True behind TLS
    impersonation_cookie: str = "schoolos_impersonation"
    cookie_domain: str | None = None

    # --- Auth behavior ---
    # When True (dev), password-reset links are returned by the API instead of emailed.
    dev_email: bool = True
    allow_email_verification_skip: bool = True

    # --- Infra ---
    use_redis: bool = False  # Phase 2: background jobs move to Celery+Redis
    storage_driver: str = "local"  # local | s3 (s3 later)
    storage_base_dir: str = ".storage"

    # --- LLM (Groq) ---
    # When GROQ_API_KEY is unset the AI engines keep working with their
    # deterministic template fallbacks (no external calls, cost $0).
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 60.0

    # --- Seeding ---
    seed_demo_school: bool = True

    def validate_production_config(self) -> None:
        """Validate that critical settings are production-ready.

        Raises ValueError if production requirements are not met.
        """
        if self.debug:
            # Debug mode enabled - skip production validation
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