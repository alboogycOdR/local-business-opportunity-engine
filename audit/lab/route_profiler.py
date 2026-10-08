"""Profile every GET route of the LBOE app against a populated database (WS-P).

For each route it records HTTP status, wall time (p50/max over ``--repeat``
runs), number of SQL statements executed, response size, and the number of
pool connections still checked out afterwards (to expose session leaks).
Path parameters are filled with real identifiers read from the database.

    LBOE_DATABASE_URL=postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe_s100 \
    python audit/lab/route_profiler.py --repeat 3 --out audit/evidence/perf/routes_s100.json
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
import time
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("APP_ROOT") or Path(__file__).resolve().parents[2])  # code under test
os.chdir(ROOT)  # static files are mounted relative to the working directory
sys.path[:0] = [
    str(ROOT / "apps/api/src"),
    str(ROOT / "packages/domain/src"),
    str(ROOT / "packages/scoring/src"),
    str(ROOT / "integrations/maps_scraper/src"),
    str(ROOT / "integrations/website_auditor/src"),
]

from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event, text  # noqa: E402

# Path parameter name -> SQL returning a representative identifier.
PARAM_SQL = {
    "campaign_id": "select campaign_id from businesses group by campaign_id order by count(*) desc limit 1",
    "business_id": "select b.id from businesses b join generated_demos d on d.business_id=b.id "
    "join proposal_packages p on p.business_id=b.id order by b.created_at limit 1",
    "audit_id": "select id from audit_runs order by started_at limit 1",
    "enrichment_id": "select id from enrichment_runs limit 1",
    "score_id": "select id from opportunity_scores order by created_at limit 1",
    "brief_id": "select id from business_briefs order by created_at limit 1",
    "demo_id": "select id from generated_demos where status='approved' order by created_at limit 1",
    "review_id": "select id from demo_reviews limit 1",
    "package_id": "select id from outreach_draft_packages limit 1",
    "log_id": "select id from outreach_execution_records limit 1",
    "event_id": "select id from lead_crm_events limit 1",
    "project_id": "select id from delivery_projects limit 1",
    "proposal_id": "select id from proposal_packages limit 1",
    "pilot_id": "select id from pilot_runs limit 1",
    "artifact_id": "select id from audit_artifacts limit 1",
    "queue_name": "select 'demo-review'",
    "token": "select 'not-a-real-token'",
}
SKIP = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=120.0, help="skip repeats once a route exceeds this")
    args = parser.parse_args()

    import lboe_api.main as app_module

    engine = app_module.engine
    statements = {"n": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _count(*_a: Any, **_k: Any) -> None:
        statements["n"] += 1

    params: dict[str, str] = {}
    with engine.connect() as conn:
        for name, sql in PARAM_SQL.items():
            value = conn.execute(text(sql)).scalar()
            if value is not None:
                params[name] = str(value)
        counts = {
            table: conn.execute(text(f"select count(*) from {table}")).scalar()  # noqa: S608 - fixed table list
            for table in ("businesses", "source_observations", "opportunity_scores", "generated_demos", "jobs")
        }

    client = TestClient(app_module.app)
    results = []
    from lboe_api.ui.routes import router as ui_router

    # Recent FastAPI versions keep included routers nested, so collect both.
    all_routes = list(app_module.app.routes) + list(ui_router.routes)
    seen: set[str] = set()
    gets = []
    for r in all_routes:
        if isinstance(r, APIRoute) and "GET" in r.methods and r.path not in SKIP and r.path not in seen:
            seen.add(r.path)
            gets.append(r)
    for route in sorted(gets, key=lambda r: r.path):
        path = route.path
        missing = [p for p in route.param_convertors if p not in params]
        if missing:
            results.append({"path": route.path, "skipped": f"no sample value for {missing}"})
            continue
        for name, value in params.items():
            path = path.replace("{" + name + "}", value)
        timings: list[float] = []
        sql_counts: list[int] = []
        size = status = 0
        leak_warnings = 0
        for _ in range(args.repeat):
            statements["n"] = 0
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                started = time.perf_counter()
                response = client.get(path, follow_redirects=False)
                elapsed = time.perf_counter() - started
                gc.collect()
                leak_warnings += sum("non-checked-in connection" in str(w.message) for w in caught)
            timings.append(elapsed)
            sql_counts.append(statements["n"])
            size, status = len(response.content), response.status_code
            if elapsed > args.timeout_s:
                break
        results.append(
            {
                "path": route.path,
                "status": status,
                "p50_ms": round(statistics.median(timings) * 1000, 1),
                "max_ms": round(max(timings) * 1000, 1),
                "sql_statements": max(sql_counts),
                "bytes": size,
                "pool_checked_out_after": engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else None,
                "gc_reclaimed_connection_warnings": leak_warnings,
            }
        )
        print(f"{results[-1].get('p50_ms', '-'):>9} ms {results[-1].get('sql_statements', '-'):>6} sql  {route.path}")
    report = {"row_counts": counts, "sample_params": params, "routes": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
