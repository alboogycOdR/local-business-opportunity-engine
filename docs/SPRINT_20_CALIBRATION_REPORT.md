# Sprint 20 — calibration report

Sprint 16 (10 leads) produced an average score of 67.6, 5 high / 2 medium / 3
low, 2 demos, 1 QA pass, and 1 approved demo. Batch 2 (21 imported leads)
produced an average score of 61.86, 8 high / 2 medium / 11 low, 4 demos, 3 QA
passes, and 3 approved demos. Both batches had zero manual contacts and zero
replies or meetings, so outcome-based weight calibration is intentionally
deferred.

Observed patterns: healthy sites with several conversion paths generally stayed
score-only or conversion/technical opportunities; no-website records with
verified identity facts were the main starter-demo candidates; HTTP/TLS issues
and weak identity should reduce confidence; and QA failures must block sharing.

Decision: retain deterministic weights and existing holds. Improve source-aware
evidence and operator explanations before changing numeric points.
