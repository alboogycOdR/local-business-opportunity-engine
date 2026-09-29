"""Bound the time an API health check can wait to acquire a database connection."""

from __future__ import annotations

import pytest
from lboe_api.config import Settings
from lboe_api.db import make_engine
from sqlalchemy.pool import StaticPool


def test_database_pool_timeout_is_configurable_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBOE_DATABASE_POOL_TIMEOUT_SECONDS", "0.1")
    assert Settings().database_pool_timeout_seconds == 0.1
    with pytest.raises(ValueError, match="between 0.1 and 10 seconds"):
        make_engine("sqlite+pysqlite:///unused.db", pool_timeout_seconds=0.05)


def test_postgres_engine_uses_configured_pool_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBOE_DATABASE_POOL_TIMEOUT_SECONDS", "0.2")
    engine = make_engine("postgresql+psycopg://user:password@localhost/db")
    try:
        assert engine.pool._timeout == 0.2
    finally:
        engine.dispose()


@pytest.mark.parametrize("database_url", ["sqlite://", "sqlite+pysqlite:///:memory:"])
def test_sqlite_keeps_static_pool_when_pool_timeout_is_configured(database_url: str) -> None:
    engine = make_engine(database_url, pool_timeout_seconds=0.2)
    try:
        assert isinstance(engine.pool, StaticPool)
    finally:
        engine.dispose()
