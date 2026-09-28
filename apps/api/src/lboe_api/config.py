"""Environment-based application settings."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
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
    auth_secret: str = "local-development-only-change-me"
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
    model_config = SettingsConfigDict(env_prefix="LBOE_", extra="ignore")
