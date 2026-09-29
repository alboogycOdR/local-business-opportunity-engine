"""Bound the time an API health check can wait to acquire a database connection."""

from __future__ import annotations

import time

import pytest
from lboe_api.config import Settings
from lboe_api.db import make_engine
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError


def test_database_pool_timeout_is_configurable_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBOE_DATABASE_POOL_TIMEOUT_SECONDS", "0.1")
    assert Settings().database_pool_timeout_seconds == 0.1
    with pytest.raises(ValueError, match="between 0.1 and 10 seconds"):
        make_engine("sqlite+pysqlite:///unused.db", pool_timeout_seconds=0.05)


def test_engine_checkout_times_out_after_configured_wait(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBOE_DATABASE_POOL_TIMEOUT_SECONDS", "0.2")
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'pool.db'}")
    held = []
    try:
        # QueuePool defaults to five connections plus ten overflow connections.
        held.extend(engine.connect() for _ in range(15))
        started = time.monotonic()
        with pytest.raises(SQLAlchemyTimeoutError):
            engine.connect()
        elapsed = time.monotonic() - started
        assert 0.15 <= elapsed < 1.0, f"checkout waited {elapsed:.3f}s for a 0.2s configured timeout"
    finally:
        for connection in held:
            connection.close()
        engine.dispose()
