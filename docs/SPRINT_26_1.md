# Sprint 26.1 — Proposal workflow operational cleanup

Added `scripts/smoke_proposals.py`, which creates a synthetic business, seeds score/brief/approved-demo prerequisites, generates and reviews a proposal, exports the five local artifacts, and scans them for secrets, raw scraper payloads, and preview tokens. PostgreSQL migrations through `0019_delivery_projects.sql` are applied by `scripts/migrate.py` and are idempotent.

Proposal packs remain operator-reviewed artifacts. LBOE does not send proposals, collect payments, create contracts, provide legal advice, sync inboxes/CRMs, or perform delivery.
