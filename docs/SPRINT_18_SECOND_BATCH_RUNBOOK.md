# Sprint 18 second-batch runbook

Use `config/pilots/cape-town-hair-salons-batch-2.yaml`. Start with 25 leads in
dry-run mode and expand to 50 only after review.

1. Start from the accepted baseline, services, migrations, seed, and smoke checks.
2. Create Batch 2, acknowledge source policy, confirm an active operator, and run readiness.
3. Discover/import 25 leads; review weak-evidence and ambiguous rows before demos.
4. Audit, score, brief, and generate demos only for eligible leads.
5. Review QA failures; require manager review before any regeneration.
6. Share only approved demos with expiring controlled links.
7. Generate drafts and readiness records; keep manual contact outside LBOE.
8. Export, retrospect, and decide whether to expand to 50.

Stop or pause if system delivery is non-zero, unexpected sending appears, more
than 30% of demos fail QA, ambiguity increases, operators cannot explain a
score, or exports contain sensitive/raw token data.
