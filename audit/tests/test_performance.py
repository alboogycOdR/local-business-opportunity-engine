"""WS-P regression tests: connection handling, query shape, pagination, indexes."""

from __future__ import annotations

import gc
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import TARGET


def test_LBOE_AUD_101_ui_routes_release_database_sessions(app_module: Any, client: Any, tmp_path: Path) -> None:
    """UI routes must return their connection to the pool when the request ends.

    Baseline: ``ui.routes.session`` returns ``SessionLocal()`` and never closes it,
    so with a one-connection pool the second request times out (production:
    15 connections stuck ``idle in transaction``, every DB route 500s).
    """
    from lboe_api.db import Base
    from lboe_api.ui import routes
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'pool.db'}", pool_size=1, max_overflow=0, pool_timeout=0.5)
    Base.metadata.create_all(engine)
    original = routes.SessionLocal
    routes.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    gc.disable()  # production servers do not run a GC pass between requests
    try:
        statuses = []
        for _ in range(4):
            try:
                statuses.append(client.get("/ui/operators").status_code)
            except Exception as exc:  # noqa: BLE001 - TestClient re-raises server errors
                statuses.append(type(exc).__name__)
        assert statuses == [200, 200, 200, 200], f"pool exhausted by leaked UI sessions: {statuses}"
        assert engine.pool.checkedout() == 0
    finally:
        gc.enable()
        routes.SessionLocal = original
        engine.dispose()


def _statements_for(client: Any, sql: Any, path: str) -> int:
    sql.reset()
    response = client.get(path)
    assert response.status_code == 200, response.text[:300]
    return int(sql.statements)


@pytest.mark.parametrize("path", ["/ui", "/ui/opportunities"])
def test_LBOE_AUD_102_dashboard_queries_do_not_grow_with_business_count(
    client: Any, seed: Any, sql: Any, path: str
) -> None:
    """Measured baseline: /ui 990 statements @100 businesses, 9,230 @1,000 (13.4 s)."""
    campaign = seed.campaign()
    for business_id in seed.businesses(campaign, 3):
        seed.score_and_brief(business_id)
    before = _statements_for(client, sql, path)
    for business_id in seed.businesses(campaign, 15):
        seed.score_and_brief(business_id)
    after = _statements_for(client, sql, path)
    assert after - before <= 5, f"{path}: {before} -> {after} SQL statements after adding 15 businesses (N+1)"


def test_LBOE_AUD_102_campaign_page_queries_do_not_grow_with_business_count(client: Any, seed: Any, sql: Any) -> None:
    """Measured baseline: 403 statements @100 businesses, 4,003 @1,000."""
    campaign = seed.campaign()
    seed.businesses(campaign, 3)
    before = _statements_for(client, sql, f"/ui/campaigns/{campaign}")
    seed.businesses(campaign, 20)
    after = _statements_for(client, sql, f"/ui/campaigns/{campaign}")
    assert after - before <= 5, f"campaign page: {before} -> {after} SQL statements (N+1)"


def test_LBOE_AUD_103_campaign_report_does_not_load_other_campaigns(client: Any, seed: Any, sql: Any) -> None:
    """build_pilot_report loads every row of ~25 tables and filters in Python."""
    busy = seed.campaign()
    seed.businesses(busy, 60)
    empty = seed.campaign()
    sql.reset()
    response = client.get(f"/v1/campaigns/{empty}/reports/pilot")
    assert response.status_code == 200
    assert sql.rows < 40, f"campaign report for an empty campaign materialised {sql.rows} ORM rows"


def test_LBOE_AUD_104_business_list_is_paginated(client: Any, seed: Any) -> None:
    campaign = seed.campaign()
    seed.businesses(campaign, 30)
    response = client.get("/v1/businesses", params={"campaign_id": campaign, "limit": 10})
    assert response.status_code == 200
    body = response.json()
    items = body["items"] if isinstance(body, dict) else body
    assert len(items) <= 10, f"limit ignored: returned {len(items)} businesses"


def _migration_indexes() -> set[tuple[str, tuple[str, ...]]]:
    found: set[tuple[str, tuple[str, ...]]] = set()
    pattern = re.compile(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s+ON\s+(\w+)\s*(?:USING\s+\w+\s*)?\(([^)]*)\)",
        re.IGNORECASE,
    )
    inline_unique = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\n\);", re.S | re.I)
    for path in sorted((TARGET / "infrastructure/database/migrations").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for table, cols in pattern.findall(text):
            found.add((table.lower(), tuple(c.strip().split()[0].lower() for c in cols.split(","))))
        for table, body in inline_unique.findall(text):
            for line in body.splitlines():
                bits = line.strip().split()
                if len(bits) > 2 and "UNIQUE" in line.upper() and not line.strip().upper().startswith("UNIQUE"):
                    found.add((table.lower(), (bits[0].lower(),)))
            for cols in re.findall(r"UNIQUE\s*\(([^)]*)\)", body, re.I):
                found.add((table.lower(), tuple(c.strip().lower() for c in cols.split(","))))
    return found


def test_LBOE_AUD_105_orm_indexes_exist_in_migrations(app_module: Any) -> None:
    """Tests use create_all (ORM indexes); production uses SQL migrations (22 indexes missing)."""
    from lboe_api.db import Base

    migrated = _migration_indexes()
    missing = sorted(
        f"{table.name}({', '.join(c.name for c in index.columns)})"
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if (table.name, tuple(c.name for c in index.columns)) not in migrated
    )
    assert not missing, f"{len(missing)} ORM indexes have no migration: {missing}"
