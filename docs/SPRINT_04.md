# Sprint 4 — Opportunity Score v1

Opportunity Score v1 is a deterministic, evidence-backed measure of
addressable digital opportunity and delivery confidence. It is not a rating
of business quality and does not use LLM judgment.

Formula:

* Addressable gap: 0–55 (website availability, conversion gaps, mobile and
  objective technical findings)
* Commercial readiness: 0–20 (active state, category/service evidence and
  verified facts)
* Reachability: 0–10 (website/phone/public availability; never consent)
* Demo confidence: 0–15 (verified identity, locality and audit evidence)

Scores are capped at 100 and banded low (0–49), medium (50–69), or high
(70–100). Healthy websites reduce rebuild priority; they do not imply a
business is weak. Every persisted score retains components, evidence,
confidence, holds, and history.

Holds include `SUPPRESSED`, `AMBIGUOUS_IDENTITY`, `NO_VERIFIABLE_CONTACT`,
and `INSUFFICIENT_FACTS_FOR_DEMO`. Suppression always produces
`do_not_contact`; ambiguity produces `manual_review`. Other actions include
`audit_required`, `generate_demo`, `technical_cleanup_offer`,
`conversion_upgrade_offer`, `score_only`, and `archive`.

Scoring a discovered business without a website is allowed as a pre-audit
read-only score and does not bypass the lifecycle. An `AUDITED` business
transitions to `SCORED` with a pipeline event.

This version is intentionally conservative and will be calibrated only from
observed pilot outcomes in a later sprint. It does not implement enrichment,
LLM intelligence, demos, offers, or outreach.

Real smoke result for Excentric on Kloof: score `45` (low band), with a
healthy-site reduction, missing H1, low image-alt coverage, browser console
errors, and failed first-party request components. Booking, WhatsApp,
click-to-call, contact form, and service catalogue were detected. The
recommended action was `score_only`; the lead transitioned to `SCORED`.
