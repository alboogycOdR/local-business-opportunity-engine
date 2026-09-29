# Docker

Root `docker-compose.yml` provides PostgreSQL, Redis, and one bounded LBOE worker.
The worker consumes Redis Stream references to PostgreSQL `jobs` rows. PostgreSQL
is authoritative for job payload, status, and result; Redis contains only the
job UUID. The worker supports `DISCOVER_CAMPAIGN`, `AUDIT_WEBSITE`, and
`ENRICH_BUSINESS`, with one consumer and one Chromium audit at a time.

The worker container has a 1 GiB memory limit and a 1 CPU limit. Audit artifacts
are written through the host bind mount `./artifacts:/app/artifacts`; with the
default API setting `audit_artifact_root='artifacts/audits'`, a host-run API and
the Compose worker see the same files under `<repository>/artifacts/audits/`.
Each browser audit stores screenshots below
`artifacts/audits/<business_id>/<artifact_run_id>/`. A worker healthcheck verifies
its poll heartbeat. The worker does not automatically retry failed or interrupted
jobs: inspect the PostgreSQL job row before an operator creates a new job, since
repeating external discovery can duplicate provider work.

Run locally with `docker compose up --build`. Redis group name and stream are
`lboe-workers` and `lboe:jobs:v1`. API integration should first commit a
`jobs` row with `status='queued'`, then publish its UUID with `XADD` to that
stream under field `job_id`. See `apps/worker/src/lboe_worker/queue.py`.

Supported `job_type` values and PostgreSQL `payload` shapes are:

- `DISCOVER_CAMPAIGN`: `DiscoveryRequest` JSON (`campaign_id`, non-empty
  `queries`, optional geography/coordinates, `max_results`, `timeout_seconds`,
  optional `idempotency_key`).
- `AUDIT_WEBSITE`: `AuditRequest` JSON (`business_id`, optional `website_url`,
  `timeout_seconds`, `max_pages`, optional `idempotency_key`).
- `ENRICH_BUSINESS`: `EnrichmentRequest` JSON (`business_id`, optional
  `website_url`, optional `idempotency_key`).

On success the worker writes `status='succeeded'` and adds `payload.result`.
Result shapes are discovery counts (`candidates`, `imported`, `duplicates`,
`ambiguous`), audit identifiers/count (`audit_run_id`, `status`,
`finding_count`), and enrichment identifiers/count (`enrichment_run_id`,
`status`, `fact_count`). On handler failure it writes `status='failed'` and
`payload.error` as the exception class name only. A queue duplicate for any row
not in `queued` status is acknowledged without execution. Interrupted `running`
jobs are intentionally left for operator inspection; there is no automatic
replay of potentially non-idempotent external work.

This host bind mount is the local development topology. A separately deployed
API and worker must use a shared persistent filesystem mounted at the same
`audit_artifact_root` in both containers, or a shared object-storage backend;
the Compose bind mount does not provide cross-host production storage.
