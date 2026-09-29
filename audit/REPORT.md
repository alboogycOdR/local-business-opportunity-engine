# LBOE Audit Report — UX, Accessibility & Performance

## 1. Header

### 1.1 Identification

| | |
|---|---|
| Repository | `alboogycOdR/local-business-opportunity-engine` |
| Audited commit | `cc56bda` (`docs: track product and sprint specifications`) |
| Date | 29 September 2026 |
| Workstreams in this pass | **WS-O** UI / UX / accessibility / content · **WS-P** performance, scalability, capacity (plus the operability items they uncovered) |
| Lab | Linux sandbox; PostgreSQL 16 + Redis 7 from the repo's own `docker-compose.yml`; synthetic data only; no external network targets |
| Tooling | Python 3.12.3, FastAPI 0.141.1, SQLAlchemy 2.1.1, Playwright 1.56.0 + Chromium 141, axe-core 4.13.0, pytest 9, ruff 0.16, mypy 2.3 (`evidence/tools/pip_freeze.txt`) |
| Reproduction | `audit/README.md` |

### 1.2 Coverage

| Workstream | Status | Notes |
|---|---|---|
| WS-O UI/UX/accessibility | **Complete** | 45 pages × 4 viewports, axe on 90 scans, keyboard pass, aria snapshots, copy and safety-legibility review, prospect preview |
| WS-P Performance/capacity | **Complete** | 10² / 10³ / 10⁴ datasets, every GET route profiled, concurrency/pool test, EXPLAIN, pipeline and Playwright cost model |
| WS-Q Operability | Partial | Only items found through WS-O/WS-P: health semantics, migration parity, timestamp storage |
| Other workstreams (WS-A…N, R, S, K) | Not run in this pass | Out of the requested focus. Leads L1–L12 are not re-litigated here. |

### 1.3 Method

Findings are backed by one of four kinds of evidence: a regression test in `audit/tests/` that **fails on
`cc56bda`**, a measurement in `audit/evidence/`, a screenshot, or an exact file:line trace. Every fix is a patch in
`audit/patches/`, verified against the regression suite, the repository's own 57 tests, `mypy` (strict, as
configured) and `ruff`. Behaviour-preserving performance rewrites were additionally checked by comparing outputs on
real databases (`tools/report_golden.py`, `tools/cards_golden.py`).

## 2. Executive summary

### 2.1 Scorecard (in-scope dimensions)

| Dimension | Baseline | With patches | One-line justification |
|---|---|---|---|
| UI/UX | **1 / 5** | 3.5 / 5 | Baseline golden path cannot be completed in the UI (no review, consent, contact or CRM controls). Patched: complete, stage-aware, with readable errors. |
| Accessibility | **2 / 5** | 4 / 5 | Baseline: contrast fails on 43/45 pages, unlabeled primary controls, no skip link. Patched: 0 axe violations across 90 scans, 0 undersized targets. |
| Performance/scalability | **1 / 5** | 3.5 / 5 | Baseline: dashboard 1.0 s at 100 leads, 13.4 s at 1k, 488 s at 10k. Patched: constant query count per page; 10k dashboard 6.3 s (77× faster); see §5. |
| Operability (as observed) | **1 / 5** | 3 / 5 | Baseline: two concurrent UI requests permanently exhaust the DB pool while `/health` stays 200. Patched: 30 concurrent requests, 0 leaked connections. |

### 2.2 Verdict

**For UX and performance, the "v1 commercial release candidate" claim does not survive.** The baseline cannot
complete its own documented workflow in the operator console. Its most important page stops responding after a
handful of concurrent requests and needs a restart. It becomes unusable (above 10 s) between roughly 500 and 1,000
leads.

The underlying architecture is sound for a small pilot: server-rendered pages, deterministic services, and the
safety gates are inside the API functions. Every defect here was fixable in place with small, testable changes.
Those changes are delivered as patches.

### 2.3 Top issues

| # | Issue | Evidence |
|---|---|---|
| 1 | **LBOE-AUD-101** — every UI request leaks a DB session. After 15 requests at concurrency ≥ 2 all database routes fail permanently (`QueuePool limit … timed out`, 15 connections `idle in transaction`) until restart; `/health` stays green. | `evidence/perf/pool_threshold_*.txt`, `pool_recovery.txt` |
| 2 | **LBOE-AUD-110** — review, consent, contact-log, CRM and follow-up steps have no UI; operators stall at `REVIEW_PENDING`. | golden-path test |
| 3 | **LBOE-AUD-102/103** — N+1 and quadratic work: dashboard 90,330 SQL statements / 488 s at 10k leads; campaign report 107 s at 10k on only 25 statements. | `evidence/perf/routes_*.json` |
| 4 | **LBOE-AUD-131 / 111** — suppression does not withdraw share links already sent, and the suppressed lead's page says "No … suppression … holds are blocking this lead" with an enrichment call to action. | tests 111, 131; screenshot |
| 5 | **LBOE-AUD-112/113** — prospects receive an unstyled preview (CSS 404) with dead links; 33% of generated concepts fail QA on ordinary names and addresses. | `evidence/ui/prospect-preview-*.jpg`, `demo_qa_false_failures.txt` |

### 2.4 Go / no-go (UX and performance lens only)

- **(a) 50-lead pilot:** **No-go on the baseline.** Operators cannot finish the workflow in the UI, and the pool
  leak will take the server down during normal use. **Go with the patches applied**, provided a single operator
  works one lead at a time: pipeline cost is about 0.3 s of server time per lead plus seconds per website audit
  (§5.4). Keep the open items in §8 on the list.
- **(b) Paid second customer:** **No-go**, even with the patches. The open items include operator identity (reviewer
  and consent decisions are typed names), long-running inline actions (LBOE-AUD-107), the report pages' Python-side
  aggregation at 10k+ (LBOE-AUD-103 residual), and the security workstreams not covered in this pass.

## 3. Findings table

| ID | Title | Severity | Confidence | WS | Status |
|---|---|---|---|---|---|
| LBOE-AUD-101 | UI DB sessions never closed → permanent pool exhaustion | Critical | Confirmed | P/Q | Fixed (patch 101) |
| LBOE-AUD-110 | Human-gated workflow steps have no UI | Critical | Confirmed | O | Fixed (patch 110-121) |
| LBOE-AUD-102 | N+1 and O(n²) on dashboard, opportunities, campaign and queue pages | High | Confirmed | P | Fixed (patch 102) |
| LBOE-AUD-103 | Reports load ~25 tables into Python with quadratic filters | High | Confirmed | P | Mitigated (patch 103); residual open |
| LBOE-AUD-131 | Suppression leaves previously shared previews live | High | Confirmed | O | Fixed (patch 131) |
| LBOE-AUD-111 | Suppressed lead presented as actionable | High | Confirmed | O | Fixed |
| LBOE-AUD-112 | Prospect preview unstyled, dead anchors, indexable/cacheable, Referer leak | High | Confirmed | O | Fixed |
| LBOE-AUD-113 | Demo QA false failures (33% of generated demos) | High | Confirmed | O | Fixed |
| LBOE-AUD-119 | Wrong times shown; aware datetimes stored without UTC normalisation; 69 columns `timestamp` vs ORM `timestamptz` | High | Confirmed | O/Q | Fixed |
| LBOE-AUD-114 | Contrast below WCAG AA on 43 pages | High | Confirmed | O | Fixed |
| LBOE-AUD-115 | Unlabeled / placeholder-only controls (WCAG 4.1.2 A) | High | Confirmed | O | Fixed |
| LBOE-AUD-104 | Unpaginated lists (`/v1/businesses`, campaign lead table) | Medium | Confirmed | P | Fixed (patch 104-105, 102) |
| LBOE-AUD-105 | 22 ORM indexes missing from migrations (tests use `create_all`) | Medium | Confirmed | P | Fixed (migration 0020) |
| LBOE-AUD-106 | `/health` stays 200 while every DB route fails; nothing restarts a wedged process | Medium | Confirmed | Q | Open |
| LBOE-AUD-107 | Audit/discovery/enrichment run inline in the request (up to 2×30 s / 300 s), per-process semaphore | Medium | Confirmed | P | Open |
| LBOE-AUD-108 | Audit screenshots overwrite a fixed per-business path; about 554 MB peak RSS per audit; no container memory limits | Medium | Confirmed | P | Open |
| LBOE-AUD-116 | No skip link, duplicate `<h1>`, content outside landmarks, `<th>` without scope, unfocusable scroll regions | Medium | Confirmed | O | Fixed |
| LBOE-AUD-117 | Undersized mobile targets (574) | Medium | Confirmed | O | Fixed |
| LBOE-AUD-118 | UUIDs as link text | Medium | Confirmed | O | Fixed |
| LBOE-AUD-120 | UI errors as raw JSON / 500 | Medium | Confirmed | O | Fixed |
| LBOE-AUD-121 | Misleading copy (verified badge, "approved" concepts, dry-run "blocked") | Medium | Confirmed | O | Fixed (copy); dry-run enforcement open |
| LBOE-AUD-122 | Dashboard failed-jobs tile always 0 | Medium | Confirmed | O | Fixed |
| LBOE-AUD-123 | "Recommended next step" ignores lifecycle stage | Medium | Confirmed | O | Fixed |
| LBOE-AUD-124 | Campaign list hides same-named campaigns | Medium | Confirmed | O | Open |
| LBOE-AUD-125 | Raw enum codes in tables and filters | Low | Confirmed | O | Partly fixed |
| LBOE-AUD-126 | No confirmation on destructive actions | Medium | Confirmed | O | Open |
| LBOE-AUD-127 | No progress feedback for long actions; double-submit | Medium | Likely | O | Open |
| LBOE-AUD-128 | Proposal approval auto-attests checks; delivery pages have no forms | Medium | Confirmed | O | Open |
| LBOE-AUD-129 | Google Maps embed: third-party data flow, empty frame when blocked | Low | Confirmed | O | Open |
| LBOE-AUD-130 | Sticky header consumes about 25% of the mobile viewport | Low | Confirmed | O | Open |

UX findings 110–131 are described in full, with wireframes, in [`UX_RECOMMENDATIONS.md`](UX_RECOMMENDATIONS.md).
The performance and operability findings are written up below.

## 4. Performance and operability findings

### LBOE-AUD-101 — UI database sessions are never closed; the server wedges permanently

- **Severity:** Critical · **Category:** performance/operability · **Confidence:** Confirmed ·
  **User impact:** every operator loses the console until someone restarts the process · **Frequency:** common
  (two concurrent requests suffice) · **Effort:** S
- **Who is affected:** operators, deployers
- **Affected:** `apps/api/src/lboe_api/ui/routes.py:75-76` (`def session() -> Session: return SessionLocal()`),
  used by 67 UI routes.
- **Description:** FastAPI only finalises generator dependencies. This one returns a new `Session` and never closes
  it. Each request autobegins a transaction and keeps its pooled connection until garbage collection. Once requests
  start failing with pool timeouts, the exception/traceback cycles keep the sessions alive. An idle server never
  runs the cyclic GC pass that would free them.
- **Reproduction:** `audit/lab/pool_threshold.sh lboe_s100 <business-id>`. Baseline results, 60 requests per level
  against `/ui/businesses/{id}` (`evidence/perf/pool_threshold_baseline_60req.txt`,
  `pool_threshold_baseline_sequential.txt`):

  | Concurrency | Baseline outcome | API afterwards | Connections `idle in transaction` |
  |---|---|---|---|
  | 1 (200 req) | run exceeded 200 s (30 s pool timeouts) | 200 | 5 |
  | 2 (200 req) | run exceeded 200 s | **500** | **15** |
  | 10 / 15 / 20 / 30 | exactly **15 × 200**, then 500s | **500** | **15** |

  Recovery was checked at +0, +50 and +100 s after load: still 15 connections stuck, `/v1/businesses/{id}` 500
  after a 30 s timeout, **`/health` 200** (`evidence/perf/pool_recovery.txt`).
  Regression test: `test_LBOE_AUD_101_ui_routes_release_database_sessions` (a one-connection pool; the second
  request times out on baseline).
- **Fix:** a generator dependency with `finally: db.close()` (`patches/LBOE-AUD-101-ui-session-leak.patch`,
  13 lines). **After the fix:** 200/200 OK at concurrency 1, 2, 5, 10, 20 and 30, peak 15 connections, **0** stuck,
  API healthy afterwards (`evidence/perf/pool_threshold_patched.txt`).
- **Related open item — LBOE-AUD-106:** `/health` should prove the process can still obtain a pool connection
  within a short timeout, and the production compose file needs a `healthcheck:` on the API so a wedged process is
  restarted.

### LBOE-AUD-102 — N+1 queries and O(n²) peer comparison on the busiest pages

- **Severity:** High · **Category:** performance · **Confidence:** Confirmed · **Effort:** M
- **Affected (baseline):** `ui/routes.py:204-439` `build_opportunity_cards` (about 9 queries per business, plus a
  per-business `SourceObservation` query, plus a nested loop comparing every business with every other); `:579-586`
  (dashboard counts every campaign's businesses with `len(...all())`); `:728-764` campaign page (4 queries per
  business, unpaginated); `:630-634` campaigns list; `:1246`, `:1293-1299` queue counts and queue pages; `:1339-1423`
  reason queues.
- **Measured:** see §5.1. The dashboard's statement count grows at about 9 per business: 990 at 100 leads, 9,230 at
  1k, 90,330 at 10k.
- **Fix** (`patches/LBOE-AUD-102-ui-n-plus-one.patch`):
  - Latest-row-per-business with one windowed query (`row_number() over (partition by business_id …)`, portable to
    SQLite).
  - Batched component, hold and observation loads.
  - An O(n) peer index that reproduces the original peer rule and tie-breaking exactly.
  - `GROUP BY` counts, and 50-row pagination on the campaign page.

  **Equivalence:** built at 100 and 1,000 leads, the Opportunity Cards have the same order and identical fields. The
  one exception is the order of *equal-point* reasons, which the baseline left to heap order (non-deterministic) and
  the patch sorts by code. Regression tests: `test_LBOE_AUD_102_*` (statement count must not grow when 15–20
  businesses are added).

### LBOE-AUD-103 — Reports load every operational table and filter in Python, quadratically

- **Severity:** High · **Category:** performance · **Confidence:** Confirmed · **Effort:** M (done) / L (residual)
- **Affected:** `reporting_service.py:88-247`. Each of about 25 tables is `select(Model)`-ed in full and filtered
  in Python, including for a single campaign. Several comprehensions rebuild a set inside their own filter
  (`if item.demo_id in {demo.id for demo in demos}`, `{str(x) for x in business_ids}` per job, `any(...)` per
  export, a set per business for `website_missing`). The dashboard called this on every load.
- **Measured:** campaign report 2.2 s at 1k and **107 s at 10k** while executing only 25 statements. A report for an
  *empty* campaign materialised 1,437 ORM rows in the regression test.
- **Fix** (`patches/LBOE-AUD-103-report-scoping.patch`, `LBOE-AUD-122-dashboard-metrics.patch`):
  - Scope every query in SQL (campaign → business IDs, chunked `IN`).
  - Build each set once.
  - Load only failed and not-eligible jobs.
  - Give the dashboard its own `COUNT`/`GROUP BY` metrics (**28 ms vs 4.2 s at 10k**).

  **Equivalence:** report JSON is identical to baseline in six variants (global, details, vertical, campaign,
  campaign+window, empty window) on the 100 and 1,000-lead datasets, re-checked after every later patch
  (`evidence/perf/report_*`).
- **Residual (open):** the report pages still materialise all *in-scope* rows: **about 5 s at 10k** (down from
  about 105 s; §5.1). The next step is an aggregate query per metric (`COUNT … GROUP BY code/status/state`),
  validated with the same golden tool.

### LBOE-AUD-104 / 105 — Unpaginated lists; ORM indexes missing from the real schema

- `/v1/businesses` returned every business with 3 queries each: 301 statements at 100 leads, 3,001 at 1k.
  **Fix:** `limit` (default 100, max 500) and `offset`, an `X-Total-Count` header, and 3 batched queries in total.
  The response shape is unchanged.
- Tests build their schema with `Base.metadata.create_all`, so they have every ORM index. Production uses the SQL
  migrations, which lack **22** of them, including `contacts(business_id)`, `businesses(identity_key)`,
  `businesses(state)` and `suppression_entries(business_id)`. Without them, a per-business contact lookup is a
  sequential scan: 0.25 ms at 1k, **1.65 ms at 10k**, executed thousands of times per page on the baseline.
  **Fix:** migration `0020_orm_index_parity.sql` (idempotent `CREATE INDEX IF NOT EXISTS`, ORM names). It was
  verified on a fresh database and twice for idempotence, and leaves zero index drift. `/v1/system/status` now
  derives the expected migration from the migrations directory instead of the hard-coded `0019_…`.
  (`evidence/tools/index_drift.txt`, `test_LBOE_AUD_105_*`)

### LBOE-AUD-107 / 108 — Long-running work inline; audit resource profile

- Discovery (up to 300 s), website audit (two page loads of up to 30 s each, plus full-page screenshots) and
  enrichment execute inside the HTTP request. The UI form blocks with no feedback. The `max_concurrency ≤ 2`
  semaphore is per process, so two API replicas mean four concurrent Chromium instances. The Redis worker described
  in the architecture does not exist (`apps/worker` is empty).
- One browser-stage audit of a light local page: **1.4 s**, **210 KB** of screenshots, **554 MB** peak RSS for the
  process tree (`evidence/perf/playwright_audit_cost.json`). The production compose file sets no memory limit.
- Screenshots are written to a fixed `artifacts/audits/<business_id>/desktop-homepage.png`
  (`playwright_auditor.py:84-87,105`). A re-audit overwrites the image that earlier `audit_artifacts` rows still
  point to, so historical evidence silently changes.
- **Recommendation:** enqueue audits to the Redis worker with a job status on the lead page. Give each run its own
  artifact directory (`…/<business_id>/<audit_run_id>/`) and cap screenshot height. Set `mem_limit` and one
  browser at a time per worker.

### Import and pipeline throughput (positive)

Import cost is flat: a 500-row chunk takes about 3.3 s at 1k and at 10k, about 6.7 ms per row, with no quadratic
dedupe at this scale. Per-lead server time through the whole pipeline is about 0.3 s, excluding the real website
audit (§5.4).

## 5. Performance dashboard

### 5.1 Route latency (p50) and SQL statements per request

Format: `latency / statements`. "base" = `cc56bda`; "patched" = all patches in `audit/patches/`. Patched 10k
includes migration 0020. The 1k patched database also has migration 0020 applied. Each run used the same host with no concurrent load.

| Route | 100 base | 1k base | 10k base | 1k patched | 10k patched |
|---|---|---|---|---|---|
| `/ui` | 1.0 s / 990 | 13.4 s / 9230 | 488.2 s / 90330 | 618 ms / 19 | 6.3 s / 29 |
| `/ui/opportunities` | 861 ms / 961 | 10.9 s / 9201 | 293.6 s / 90301 | 555 ms / 11 | 5.8 s / 21 |
| `/ui/campaigns/{campaign_id}` | 342 ms / 403 | 3.3 s / 4003 | 41.4 s / 40003 | 103 ms / 7 | 1.3 s / 11 |
| `/ui/queues/no-demo-reason` | 172 ms / 201 | 1.7 s / 2001 | 14.9 s / 20001 | 57 ms / 3 | 635 ms / 5 |
| `/ui/queues/weak-evidence` | 98 ms / 101 | 828 ms / 1001 | 7.4 s / 10001 | 37 ms / 2 | 548 ms / 3 |
| `/ui/queues` | 13 ms / 6 | 24 ms / 6 | 94 ms / 6 | 14 ms / 6 | 23 ms / 6 |
| `/ui/campaigns` | 8 ms / 2 | 19 ms / 2 | 136 ms / 2 | 14 ms / 2 | 10 ms / 2 |
| `/ui/businesses/{business_id}` | 25 ms / 17 | 33 ms / 17 | 213 ms / 17 | 32 ms / 21 | 43 ms / 21 |
| `/ui/reports/pilot` | 129 ms / 25 | 2.3 s / 25 | 102.3 s / 25 | 418 ms / 25 | 5.0 s / 41 |
| `/ui/campaigns/{campaign_id}/reports/pilot` | 88 ms / 25 | 2.1 s / 25 | 107.5 s / 25 | 423 ms / 25 | 5.0 s / 41 |
| `/v1/reports/pilot` | 93 ms / 25 | 2.2 s / 25 | 103.8 s / 25 | 432 ms / 25 | 4.9 s / 41 |
| `/v1/businesses` | 266 ms / 301 | 2.7 s / 3001 | 30.8 s / 30001 | 27 ms / 5 | 40 ms / 5 |

Generated by `audit/tools/perf_table.py` from `evidence/perf/routes_*.json`. Migration 0020 applied to the populated 10k database in 0.3 s (`evidence/perf/migration_0020_on_10k.txt`).

### 5.2 Scale curve (baseline)

| Leads | Dashboard `/ui` | Statements | Growth |
|---|---|---|---|
| 100 | 1.0 s | 990 | — |
| 1,000 | 13.4 s | 9,230 | ×13 time for ×10 data |
| 10,000 | 488 s | 90,330 | ×36 time for ×10 data (O(n²) peer loop) |

### 5.3 Concurrency

See LBOE-AUD-101: the baseline wedges at 2 concurrent UI requests; the patched build sustains 30 with no leaked
connections.

### 5.4 Capacity statement

Measured per-lead server time, p50 over the 10k generation run: import 6.7 ms, audit persistence 30 ms, score
31 ms, brief 36 ms, demo 37 ms, review 30 ms, draft 37 ms, readiness 30 ms, contact log 21 ms, CRM event 18 ms,
proposal 42 ms. That totals about **0.3 s per lead**, plus the real website audit (about 1.4 s browser time on a
light local page; seconds to tens of seconds on real sites; about 554 MB RSS each).

- **Safe pilot size on the documented single-host deployment, with patches:** 50–500 leads per campaign and a
  handful of operators. A 50-lead pilot needs under a minute of server time plus roughly 5–25 minutes of sequential
  audits.
- **Baseline:** not safe at any size with more than one browser tab (LBOE-AUD-101). Page latency passes 10 s
  between roughly 500 and 1,000 leads.
- **First three scaling changes beyond that:**
  1. Move audit, discovery and enrichment to the Redis worker with job status and one browser per worker
     (LBOE-AUD-107/108).
  2. Aggregate-only reporting with SQL `GROUP BY`, or maintained counters (LBOE-AUD-103 residual).
  3. Precompute Opportunity Cards per business when evidence changes, so the dashboard reads the top N instead of
     ranking every business per request (keyset pagination on all lists).

## 6. Seeded leads touched by this pass

| Lead | Verdict | Evidence |
|---|---|---|
| L9 (CI install / pytest-asyncio / mypy) | **CONFIRMED** | `evidence/tools/L9_documented_install.txt`, `pytest_without_pytest_asyncio.txt`, `mypy_ci.txt` (4 errors). Patched tree: `mypy` 0 errors. |
| L11 (CWD-relative static dir) | **CONFIRMED** | `uvicorn lboe_api.main:app` fails without the Dockerfile's `PYTHONPATH`; the lab scripts `cd` to the checkout for static files (`lab/serve.sh`). |
| Q1 (monolithic route files, f-string HTML) | **CONFIRMED** | 2,289-line `ui/routes.py`, about 208 hand-written escape calls; recommendation in `UX_RECOMMENDATIONS.md` §5 |
| Q2 (`__import__`, `type: ignore`, `len(...all())`) | **CONFIRMED** | Removed in patch 102 (queue counts, campaigns list) |
| Q3 (inline jobs, empty worker) | **CONFIRMED** | LBOE-AUD-107 |
| Q4 (SQLite tests vs Postgres migrations) | **CONFIRMED** | Structural schema parity is good (0 table, column, nullability or FK drift: `evidence/tools/schema_drift.json`), but 22 indexes and 69 timestamp column types differ (`schema_types_ondelete.txt`); fixed by 0020 and `UtcDateTime` |
| Q5 (no accessibility markup) | **CONFIRMED** | §2 of `UX_RECOMMENDATIONS.md` |

## 7. Unconfirmed hypotheses and areas not reached

- **Real-website audit cost** was measured on a benign local page only. Real sites were deliberately not contacted.
  Costs for heavy pages (very tall full-page screenshots, slow third-party assets) are extrapolated.
- **Screen reader:** evaluated through Playwright aria snapshots (`evidence/ui/ui_audit.json` → `aria_snapshots`),
  not with NVDA or VoiceOver.
- **Lighthouse** was not run; axe-core covers the WCAG rules. Soak testing (≥ 30 min) was not run; the pool test
  covers the leak it would have surfaced.
- **Multi-replica migration race** (the container `CMD` runs `migrate.py` on every start with no advisory lock) was
  identified by reading the code, not reproduced.
- **Security workstreams:** not part of this pass.

## 8. Remediation roadmap

| Priority | Item | Effort | Status |
|---|---|---|---|
| **Before any real pilot** | 101 session leak | S | Patch ready |
| | 110 workflow UI · 111/131 suppression legibility and link withdrawal | M | Patch ready |
| | 112/113 prospect preview and demo QA | S | Patch ready |
| | 119 timestamps · 102/104/105 query shape, pagination, indexes · 122/123 dashboard accuracy and next step | M | Patch ready |
| | 106 real health check + compose `healthcheck:` | S | Open |
| **Before v1** | 114–118, 120, 121 accessibility and copy | S–M | Patch ready |
| | 107/108 move audits to the worker; per-run artifact directories; memory limits | M–L | Open |
| | 103 residual: aggregate reporting | M | Open |
| | 126 confirmations · 127 progress feedback · 128 proposal/delivery forms · 124 campaign list | M | Open |
| **Hardening backlog** | 125 labels for all enum codes; R4–R6 queue/inbox, table sorting, mobile nav (UX doc §4); Jinja2 migration (UX doc §5); 129 maps embed opt-in | M | Open |

## 9. Positive findings (preserve these)

- **Safety gates live in the API functions** (`create_outreach_readiness`, `create_outreach_log`, `review_demo`).
  The new UI forms call those same functions, so every gate applied to API calls also applies to the UI.
- **No sending path exists.** Every contact is recorded as an operator assertion with
  `delivery_performed_by_system: false`.
- **Post/Redirect/Get** on every UI POST; refresh never resubmits a form.
- **The report's timestamp windowing** (`_in_window`) already normalises naive and aware values correctly on
  Postgres: a suspected date-filter crash was **refuted**.
- **Schema parity** of tables, columns, nullability and FKs between the ORM and 19 migrations is exact, and
  `migrate.py` is idempotent.
- **Concept preview markup** has zero axe violations, and the preview token design (32-byte `token_urlsafe`, stored
  SHA-256) is sound.
- **Import dedupe** scales linearly in the measured range.
