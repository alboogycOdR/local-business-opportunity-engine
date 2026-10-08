"""Synthetic LBOE dataset generator for UX and performance audits (WS-O / WS-P).

Drives the *real* application routes in-process (FastAPI TestClient) so every
record is produced by production code paths.  The only substitution is the
website audit adapter, replaced by a deterministic offline adapter so no
network request is ever made.  All businesses, phones and domains are
synthetic (``.example`` / ``.test`` TLDs, 555-style numbers).

Usage (database must already be migrated with scripts/migrate.py):

    LBOE_DATABASE_URL=postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe_s100 \
    LBOE_DEMO_ARTIFACT_ROOT=/tmp/lboe-artifacts LBOE_EXPORT_ROOT=/tmp/lboe-exports \
    python audit/lab/datagen.py --businesses 100 --worked 40 --timings out.json

``--businesses`` rows are imported; ``--worked`` of them are pushed through the
pipeline (audit → score → brief → demo → review → draft → readiness → contact
→ CRM → proposal → delivery) with a deterministic spread of end states; the
rest are scored and briefed only for a ``--scored-fraction`` share.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "apps/api/src"),
    str(ROOT / "packages/domain/src"),
    str(ROOT / "packages/scoring/src"),
    str(ROOT / "integrations/maps_scraper/src"),
    str(ROOT / "integrations/website_auditor/src"),
]

from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_audit import OfflineAuditAdapter  # noqa: E402

PREFIXES = [
    "Studio",
    "Salon",
    "Kapsalon",
    "Hair",
    "Mooi",
    "Glow",
    "Urban",
    "Blue Door",
    "Crown & Co",
    "Lekker",
    "Anne's",
    "Die Haarhuis",
    "Fynbos",
    "Table Mountain",
    "Bo-Kaap",
    "Atlantic",
    "Sea Point",
    "Observatory",
]
SUFFIXES = ["Hair", "Beauty", "Cuts", "Styling", "Barbers", "Nails", "Spa", "Hair & Beauty", "Kappers", "Studio"]
LOCALITIES = [
    "Sea Point",
    "Observatory",
    "Woodstock",
    "Claremont",
    "Rondebosch",
    "Bellville",
    "Durbanville",
    "Stellenbosch",
    "Muizenberg",
    "Gardens",
    "Green Point",
    "Khayelitsha",
    "Mitchells Plain",
    "Parow",
]
STREETS = ["Main Road", "Regent Road", "Lower Main Road", "Kloof Street", "Voortrekker Road", "R44", "Long Street"]
CATEGORIES = ["Hair salon", "Barber shop", "Beauty salon", "Nail salon", "Day spa"]


def synthetic_row(rng: random.Random, index: int) -> dict[str, Any]:
    name = f"{rng.choice(PREFIXES)} {rng.choice(SUFFIXES)} {index:05d}"
    locality = rng.choice(LOCALITIES)
    row: dict[str, Any] = {
        "display_name": name,
        "category": rng.choice(CATEGORIES),
        "locality": locality,
        "address_text": f"Shop {rng.randint(1, 40)}, Floor {rng.randint(1, 3)}, {rng.randint(1, 400)} "
        f"{rng.choice(STREETS)}, {locality}, Cape Town",
        "phone": f"+27 21 555 {index % 10000:04d}" if rng.random() < 0.85 else "",
        "rating": f"{rng.uniform(3.0, 5.0):.1f}" if rng.random() < 0.8 else "",
        "review_count": str(rng.randint(0, 400)) if rng.random() < 0.8 else "",
        "source_ref": f"synthetic://lboe-audit/{index}",
    }
    if rng.random() < 0.55:
        row["website"] = f"https://salon-{index:05d}.example"
    return row


class Timer:
    def __init__(self) -> None:
        self.samples: dict[str, list[float]] = defaultdict(list)

    def call(self, label: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        result = fn(*args, **kwargs)
        self.samples[label].append(time.perf_counter() - started)
        return result

    def summary(self) -> dict[str, dict[str, float]]:
        out = {}
        for label, values in self.samples.items():
            ordered = sorted(values)
            out[label] = {
                "n": len(values),
                "p50_ms": round(statistics.median(ordered) * 1000, 1),
                "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)] * 1000, 1),
                "max_ms": round(ordered[-1] * 1000, 1),
                "total_s": round(sum(values), 2),
            }
        return out


def ok(response: Any, label: str) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(f"{label}: HTTP {response.status_code}: {response.text[:300]}")
    return response.json()  # type: ignore[no-any-return]


CHECKLIST = [
    "concept_banner_visible",
    "business_name_correct",
    "not_claiming_official_site",
    "no_fake_prices",
    "no_fake_testimonials",
    "no_unsupported_awards",
    "contact_links_safe",
    "source_claims_supported",
    "no_outreach_content",
    "appropriate_demo_type",
    "preview_opens_locally",
    "no_sensitive_or_prohibited_content",
]


def work_lead(client: TestClient, timer: Timer, business_id: str, depth: int, stats: dict[str, int]) -> None:
    """Push one lead through the pipeline, stopping after ``depth`` stages."""
    b = f"/v1/businesses/{business_id}"
    timer.call("POST audit", client.post, f"{b}/audit", json={"idempotency_key": "lab"})
    timer.call("POST score", client.post, f"{b}/score", json={"idempotency_key": "lab"})
    ok(timer.call("POST brief", client.post, f"{b}/brief", json={"idempotency_key": "lab"}), "brief")
    if depth < 2:
        return
    demo = ok(timer.call("POST demo", client.post, f"{b}/demo", json={"idempotency_key": "lab"}), "demo")
    if demo.get("status") != "qa_passed":
        stats[f"demo:{demo.get('status')}:{demo.get('reason', '')}"] += 1
        return
    stats["demo:qa_passed"] += 1
    if depth < 3:
        return
    review = timer.call(
        "POST demo review",
        client.post,
        f"/v1/demos/{demo['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "lab-operator",
            "notes": "synthetic",
            "checklist": [{"code": code, "label": code.replace("_", " "), "passed": True} for code in CHECKLIST],
        },
    )
    if review.status_code != 200:
        stats[f"review_blocked:{review.json().get('detail')}"] += 1
        return
    stats["demo:approved"] += 1
    if depth < 4:
        return
    draft = ok(
        timer.call(
            "POST outreach-draft",
            client.post,
            f"{b}/outreach-draft",
            json={"channels": ["email", "whatsapp"], "idempotency_key": "lab"},
        ),
        "draft",
    )
    if "id" not in draft:
        stats[f"draft:{draft.get('reason')}"] += 1
        return
    if draft["status"] != "ready":
        stats["draft:blocked_by_safety_checks"] += 1
        return
    readiness = ok(
        timer.call(
            "POST readiness",
            client.post,
            f"{b}/outreach-readiness",
            json={
                "outreach_draft_package_id": draft["id"],
                "decision": "prepare_consent_review",
                "reviewer": "lab-operator",
            },
        ),
        "readiness",
    )
    if depth < 5 or readiness.get("status") == "not_outreach_ready_eligible":
        return
    approve = ok(
        timer.call(
            "POST readiness",
            client.post,
            f"{b}/outreach-readiness",
            json={
                "outreach_draft_package_id": draft["id"],
                "decision": "approve_for_manual_outreach",
                "reviewer": "lab-operator",
                "selected_channels": ["email"],
                "consent_basis_type": "public_business_contact_for_manual_outreach",
                "consent_basis_notes": "synthetic lab record",
            },
        ),
        "readiness approve",
    )
    if depth < 6 or approve.get("status") == "not_outreach_ready_eligible":
        return
    message = next(m for m in draft["messages"] if m["channel"] == "email")
    log = ok(
        timer.call(
            "POST outreach-log",
            client.post,
            f"{b}/outreach-log",
            json={
                "outreach_draft_package_id": draft["id"],
                "outreach_draft_message_id": message["id"],
                "channel": "email",
                "operator": "lab-operator",
                "sent_at": datetime.now(UTC).isoformat(),
                "notes": "synthetic",
            },
        ),
        "outreach log",
    )
    stats["contacted"] += 1
    if depth < 7:
        return
    now = datetime.now(UTC)
    for offset, event in enumerate(("reply_received", "meeting_scheduled", "proposal_sent")):
        ok(
            timer.call(
                "POST crm-event",
                client.post,
                f"{b}/crm-event",
                json={
                    "event_type": event,
                    "channel": "email",
                    "operator": "lab-operator",
                    "occurred_at": (now + timedelta(minutes=offset)).isoformat(),
                    "summary": f"synthetic {event}",
                    "outreach_execution_record_id": log.get("id"),
                },
            ),
            event,
        )
    proposal = ok(
        timer.call("POST proposal", client.post, f"{b}/proposal", json={"idempotency_key": "lab"}), "proposal"
    )
    if "id" in proposal:
        ok(
            client.post(f"/v1/proposals/{proposal['id']}/review", json={"decision": "approve", "reviewer": "lab"}),
            "proposal review",
        )
        ok(
            client.post(
                f"{b}/delivery-project", json={"proposal_package_id": proposal["id"], "title": "Synthetic build"}
            ),
            "delivery",
        )
        stats["delivery_project"] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--businesses", type=int, default=100)
    parser.add_argument("--worked", type=int, default=40, help="leads pushed deeper into the pipeline")
    parser.add_argument("--scored-fraction", type=float, default=0.5, help="share of remaining leads scored+briefed")
    parser.add_argument("--seed", type=int, default=20260929)
    parser.add_argument("--timings", type=Path, help="write per-step timing JSON here")
    args = parser.parse_args()

    import lboe_api.main as app_module

    app_module.set_audit_adapter(OfflineAuditAdapter())
    client = TestClient(app_module.app)
    rng = random.Random(args.seed)
    timer = Timer()
    stats: dict[str, int] = defaultdict(int)
    started = time.perf_counter()

    campaign = ok(
        client.post(
            "/v1/campaigns",
            json={"name": f"Audit lab {args.businesses}", "vertical": "hair-salon", "geography": "Cape Town"},
        ),
        "campaign",
    )
    ids: list[str] = []
    rows = [synthetic_row(rng, i) for i in range(args.businesses)]
    for start in range(0, len(rows), 500):
        chunk = rows[start : start + 500]
        result = ok(
            timer.call(
                "POST import (500 rows)",
                client.post,
                f"/v1/campaigns/{campaign['id']}/import",
                json={"format": "json", "records": chunk, "source_type": "synthetic_audit_lab"},
            ),
            "import",
        )
        ids.extend(item["business_id"] for item in result["successes"])
        stats["import_failures"] += result["failed"]

    # A local operator and pilot so every operator page has data.
    client.post("/ui/operators", data={"display_name": "Lab Operator", "role": "owner"}, follow_redirects=False)
    client.post(
        "/ui/pilots",
        data={"name": f"Lab pilot {args.businesses}", "campaign_id": campaign["id"], "mode": "dry_run"},
        follow_redirects=False,
    )

    worked = ids[: args.worked]
    for position, business_id in enumerate(worked):
        # Deterministic spread of depths so every lifecycle stage is populated.
        work_lead(client, timer, business_id, depth=1 + position % 7, stats=stats)
    rest = ids[args.worked :]
    for business_id in rest[: int(len(rest) * args.scored_fraction)]:
        timer.call("POST score", client.post, f"/v1/businesses/{business_id}/score", json={"idempotency_key": "lab"})
        timer.call("POST brief", client.post, f"/v1/businesses/{business_id}/brief", json={"idempotency_key": "lab"})

    # A few suppressions and comments for the safety/UX review.
    for business_id in worked[2::9]:
        client.post(f"/v1/businesses/{business_id}/suppressions", json={"reason": "synthetic opt-out"})
        stats["suppressed"] += 1
    for business_id in worked[:5]:
        client.post(f"/ui/businesses/{business_id}/comment", data={"body": "Synthetic note"}, follow_redirects=False)

    elapsed = time.perf_counter() - started
    report = {
        "campaign_id": campaign["id"],
        "businesses": len(ids),
        "worked": len(worked),
        "elapsed_s": round(elapsed, 1),
        "outcomes": dict(sorted(stats.items())),
        "timings": timer.summary(),
        "sample_business_id": worked[0] if worked else None,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": str(uuid.uuid4()),
    }
    if args.timings:
        args.timings.parent.mkdir(parents=True, exist_ok=True)
        args.timings.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
