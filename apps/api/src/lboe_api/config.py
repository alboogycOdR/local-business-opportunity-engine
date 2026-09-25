"""Environment-based application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
    redis_url: str = "redis://localhost:6379/0"
    model_config = SettingsConfigDict(env_prefix="LBOE_", extra="ignore")
