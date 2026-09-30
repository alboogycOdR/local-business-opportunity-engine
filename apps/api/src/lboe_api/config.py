"""Environment-based application settings."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_AUTH_SECRET = "local-development-only-change-me"


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
    database_pool_timeout_seconds: float = Field(default=2.0, ge=0.1, le=10.0)
    redis_url: str = "redis://localhost:6379/0"
    auto_create_schema: bool = False
    maps_scraper_enabled: bool = Field(
        default=False, validation_alias=AliasChoices("LBOE_FEATURE_MAPS_SCRAPER", "FEATURE_MAPS_SCRAPER")
    )
    discovery_kill_switch: bool = False
    maps_scraper_url: str = "http://localhost:8080"
    discovery_poll_interval_seconds: float = 2.0
    discovery_max_concurrency: int = 1
    discovery_timeout_seconds: float = 300.0
    audit_artifact_root: str = "artifacts/audits"
    audit_max_concurrency: int = 1
    demo_artifact_root: str = "artifacts"
    export_root: str = "exports"
    auth_enabled: bool = False
    auth_secret: str = DEFAULT_AUTH_SECRET
    operator_auth_token: str = ""
    secure_cookies: bool = False
    csrf_enabled: bool = False
    storage_backend: str = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "auto"
    signed_url_ttl_seconds: int = 900
    # Operator-facing times are rendered in this IANA zone (storage stays UTC).
    display_timezone: str = "Africa/Johannesburg"
    model_config = SettingsConfigDict(env_prefix="LBOE_", extra="ignore")


def production_security_errors(settings: Settings) -> list[str]:
    """Return fail-closed configuration errors for a production deployment."""
    if settings.environment.casefold() not in {"production", "prod"}:
        return []
    errors: list[str] = []
    if not settings.auth_enabled:
        errors.append("LBOE_AUTH_ENABLED must be true")
    if len(settings.operator_auth_token) < 32:
        errors.append("LBOE_OPERATOR_AUTH_TOKEN must contain at least 32 characters")
    if settings.auth_secret == DEFAULT_AUTH_SECRET or len(settings.auth_secret) < 32:
        errors.append("LBOE_AUTH_SECRET must be a non-default value of at least 32 characters")
    if not settings.secure_cookies:
        errors.append("LBOE_SECURE_COOKIES must be true")
    if not settings.csrf_enabled:
        errors.append("LBOE_CSRF_ENABLED must be true")
    return errors
