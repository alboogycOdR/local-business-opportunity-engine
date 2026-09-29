# LBOE audit workspace — UX/accessibility (WS-O) and performance (WS-P)

Everything needed to reproduce the findings in [`REPORT.md`](REPORT.md) and to verify the proposed fixes in
[`patches/`](patches). Nothing in this directory modifies the audited application code: fixes are delivered as
patches and verified in a separate checkout.

- **Audited commit:** `cc56bda` (`docs: track product and sprint specifications`)
- **Scope of this pass:** UX, accessibility and performance, as requested. The security workstreams from the
  original audit prompt were not executed in this pass (see `REPORT.md` §1.3).

## 1. Layout

| Path | Purpose |
|---|---|
| `REPORT.md` | Findings, measurements, before/after results, capacity statement, roadmap |
| `UX_RECOMMENDATIONS.md` | UX defect list, redesign recommendations and wireframes |
| `tests/` | Regression suite: every test is named after its finding, **fails on `cc56bda`**, passes with the patches |
| `patches/` | One patch per root cause plus `ALL-combined.patch`; apply in the order listed in §4 |
| `lab/datagen.py` | Synthetic dataset generator that drives the real API in-process (offline audit adapter, no network) |
| `lab/offline_audit.py` | Deterministic, network-free audit adapter |
| `lab/route_profiler.py` | Every GET route: latency, SQL statement count, bytes, pool state |
| `lab/load_test.py`, `lab/pool_threshold.sh` | Concurrency test with `pg_stat_activity` sampling (session-leak proof) |
| `lab/ui_audit.py` | Playwright sweep: 45 pages × 4 viewports, axe-core, overflow, target size, headings, keyboard |
| `lab/axe_static.py` | axe-core on saved HTML (for CSP-protected concept previews) |
| `lab/audit_cost.py` | Cost of one Playwright homepage audit against a benign local page |
| `lab/serve.sh`, `lab/restart.sh`, `lab/reset_db.sh` | Run any checkout (`APP_ROOT=`) against a scratch database |
| `tools/schema_drift.py` | ORM metadata vs migrated PostgreSQL (tables, columns, nullability, FKs) |
| `tools/report_golden.py`, `tools/cards_golden.py` | Before/after output equivalence for the performance rewrites |
| `evidence/` | Raw outputs: `perf/`, `ui/` (baseline: 45 pages × 4 viewports + axe), `ui-patched/` (after patches: metrics for all 4 viewports, screenshots kept for desktop and mobile), `LBOE-AUD-UX/`, `tools/` |

## 2. Environment used

- Linux, Python 3.12.3 (`uv venv -p 3.12 .venv-audit`), Docker 29 (repo `docker-compose.yml`: PostgreSQL 16, Redis 7)
- FastAPI 0.141.1, Starlette 1.7.0, SQLAlchemy 2.1.1, Pydantic 2.13.5, httpx 0.28.1 — full list in
  `evidence/tools/pip_freeze.txt`. **Playwright pinned to 1.56.0** so it matches the pre-installed Chromium build;
  the repo's floor pin `playwright>=1.50` resolved to 1.63 and could not launch a browser.
- axe-core 4.13.0 (npm)

```bash
uv venv -p 3.12 .venv-audit
uv pip install --python .venv-audit/bin/python fastapi "uvicorn[standard]" pydantic-settings sqlalchemy \
  "psycopg[binary]" redis alembic httpx "playwright==1.56.0" beautifulsoup4 python-multipart \
  pytest pytest-asyncio ruff mypy hypothesis psutil
npm install --prefix /tmp/axe axe-core@4          # AXE=/tmp/axe/node_modules/axe-core/axe.min.js
docker compose up -d postgres redis
```

> `pip install -e ".[dev]"` (the documented/CI install) fails at `cc56bda` — hatchling cannot find a package
> (`evidence/tools/L9_documented_install.txt`). The lab therefore sets `PYTHONPATH` exactly like the Dockerfile.

## 3. Reproduce the measurements

```bash
# Datasets (each ~15 s / 76 s / 460 s)
for s in 100 1000 10000; do audit/lab/reset_db.sh lboe_s$s; done
LBOE_DATABASE_URL=postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe_s100 \
  .venv-audit/bin/python audit/lab/datagen.py --businesses 100 --worked 60 --timings audit/evidence/perf/datagen_s100.json
# (1000: --worked 200; 10000: --worked 300 --scored-fraction 0.5)

# Route profile (APP_ROOT selects the checkout under test)
LBOE_DATABASE_URL=...lboe_s1000 .venv-audit/bin/python audit/lab/route_profiler.py --repeat 2 --out out.json

# Connection-pool wedge (baseline) vs fix (patched checkout)
audit/lab/pool_threshold.sh lboe_s100 <business-uuid>
APP_ROOT=/path/to/patched OUT=patched.txt LEVELS="1 2 5 10 20 30" REQUESTS=200 audit/lab/pool_threshold.sh lboe_s100 <uuid>

# UI sweep (server on :8001)
audit/lab/restart.sh lboe_s100 8001
cd audit/evidence/ui && ../../../.venv-audit/bin/python ../../lab/ui_audit.py \
  --base http://127.0.0.1:8001 --pages pages.json --axe "$AXE" --out .
```

## 4. Verify the fixes

```bash
# Baseline: 40 of 43 audit tests fail (the 3 passes guard pages that already label their inputs)
.venv-audit/bin/pytest -c audit/tests/pytest.ini audit/tests

# Patched checkout
git worktree add --detach /tmp/lboe-patched cc56bda
cd /tmp/lboe-patched
for p in 101-ui-session-leak 104-105-pagination-and-index-parity 103-report-scoping \
         102-ui-n-plus-one 110-121-ux-accessibility-workflow 122-dashboard-metrics \
         123-stage-aware-next-step 131-suppression-withdraws-share-links; do
  git apply /path/to/repo/audit/patches/LBOE-AUD-$p.patch
done
cd - && LBOE_AUDIT_TARGET=/tmp/lboe-patched .venv-audit/bin/pytest -c audit/tests/pytest.ini audit/tests   # all pass
(cd /tmp/lboe-patched && ../path/.venv-audit/bin/pytest && ../path/.venv-audit/bin/mypy apps packages tests)
```

Results recorded for this pass: patched checkout — audit suite **43/43 pass**, repository suite **57 passed**,
`mypy` **0 errors** (baseline: 4), `ruff check` / `ruff format --check` clean.
