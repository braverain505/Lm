"""Application settings — loaded from environment / .env (pydantic-settings)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Application ---
    app_name: str = "Lumo API"
    debug: bool = False
    api_base_path: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://lumodemo.vercel.app",
    ]

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