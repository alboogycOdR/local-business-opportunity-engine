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
    model_config = SettingsConfigDict(env_prefix="LBOE_", extra="ignore")
