# Sprint 5 — Business Intelligence Brief

The Business Brief is a deterministic, source-backed operator object. It
does not generate marketing copy, a demo, an offer, or outreach. It assembles
verified canonical facts, contacts, external identities, website resolution,
audit findings, score components, and holds into a historical brief.

Facts are marked verified or unknown and carry source type, confidence, and
evidence references. Opportunities and risks are neutral descriptions of
observable digital conditions. Subjective language such as “ugly”, “bad
business”, or “unprofessional” is prohibited.

Recommended actions map deterministically from the score and holds:

* `score_only` → no immediate demo; review cleanup or archive
* `technical_cleanup_offer` → consider technical/accessibility/SEO hygiene
* `conversion_upgrade_offer` → consider a conversion upgrade concept
* `generate_demo` → eligible for concept demo generation
* `manual_review` → manual review required
* `do_not_contact` → suppression/policy hold; do not contact
* `audit_required` → audit before recommendation

Briefs are append-only and created through a durable `GENERATE_BRIEF` job
with idempotency. Sprint 6 can consume the verified facts, opportunities, and
evidence without inventing claims. No LLM is required or enabled in Sprint 5.

The real Excentric on Kloof smoke brief used score `45` / `low`, recommended
`score_only`, and recorded a healthy site with booking, WhatsApp, click-to-call,
contact form, and service catalogue paths. It also surfaced missing H1,
image-alt gaps, browser console errors, and a failed first-party request.
