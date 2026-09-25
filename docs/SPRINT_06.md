# Sprint 6 — Concept Demo Generator

Sprint 6 adds a deterministic, template-first concept preview generator. A
concept demo is a local static artifact for operator review; it is not a
production website, client deployment, official business site, outreach
message, or endorsement.

Generation consumes the latest Business Brief and is eligible only for
`generate_demo`, `conversion_upgrade_offer`, or `technical_cleanup_offer`.
Suppression, `do_not_contact`, ambiguous identity, insufficient facts, and
`score_only` block generation. Excentric on Kloof therefore remains
not-demo-eligible because its healthy audited site is `score_only`.

The `hair_salon_starter` template uses verified name/category/location/contact
facts plus labelled generic or placeholder copy. It never invents prices,
reviews, awards, staff, years in business, or unsupported services. A
conversion-upgrade and technical-cleanup demo type use the same safe anatomy
with an explicit type for later template refinement.

Artifacts are written to `artifacts/demos/{demo_id}/index.html`,
`styles.css`, and `metadata.json`. QA checks the independent concept banner,
business name, evidence on claims, prohibited promotional language, fake
prices/testimonials, missing files, external forms, tracking scripts, and
safe local CTA placeholders. QA failure prevents lifecycle progression.

Successful demos move `SCORED → DEMO_QUEUED → DEMO_GENERATED →
REVIEW_PENDING`; no outreach or public publication occurs. History is
append-only in the generated demo, section, claim, artifact, and QA tables.

The generator is intentionally limited to static HTML/CSS, one page, local
artifact storage, deterministic copy, and operator review. Sprint 7 can add
the human review workflow without turning this preview into delivery.
