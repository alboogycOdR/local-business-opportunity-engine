"""Drive the safe happy-path pilot flow through the local API.

No provider calls or message delivery are performed. The outreach step is an
explicit operator log with ``delivery_performed_by_system=false``.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

import httpx

CHECKLIST_CODES = (
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
)


def call(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def run(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=30) as client:
        campaign = call(
            client,
            "POST",
            "/v1/campaigns",
            json={"name": "Smoke Pilot", "vertical": "hair_salon", "geography": "Cape Town"},
        )
        campaign_id = campaign["id"]
        imported = call(
            client,
            "POST",
            f"/v1/campaigns/{campaign_id}/import",
            json={
                "format": "json",
                "source_type": "manual",
                "records": [
                    {
                        "display_name": "Smoke Concept Salon",
                        "category": "hair salon",
                        "locality": "Cape Town",
                        "address_text": "Synthetic Cape Town",
                        "phone": "+27000000000",
                    }
                ],
            },
        )
        business_id = imported["successes"][0]["business_id"]
        for state in ("DEDUPED", "QUALIFIED", "ENRICHING", "ENRICHED", "AUDITING", "AUDITED"):
            call(
                client,
                "POST",
                f"/v1/businesses/{business_id}/transition",
                json={"to_state": state, "actor": "smoke-script"},
            )
        score = call(
            client, "POST", f"/v1/businesses/{business_id}/score", json={"idempotency_key": "sprint13-smoke-score"}
        )
        brief = call(
            client, "POST", f"/v1/businesses/{business_id}/brief", json={"idempotency_key": "sprint13-smoke-brief"}
        )
        demo = call(
            client, "POST", f"/v1/businesses/{business_id}/demo", json={"idempotency_key": "sprint13-smoke-demo"}
        )
        checklist = [{"code": code, "label": code.replace("_", " "), "passed": True} for code in CHECKLIST_CODES]
        call(
            client,
            "POST",
            f"/v1/demos/{demo['id']}/review",
            json={"decision": "approve", "reviewer": "smoke-operator", "checklist": checklist},
        )
        package = call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/outreach-draft",
            json={"idempotency_key": "sprint13-smoke-draft"},
        )
        call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "prepare_consent_review",
                "reviewer": "smoke-operator",
                "consent_basis_type": "manual_operator_review",
            },
        )
        call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "approve_for_manual_outreach",
                "reviewer": "smoke-operator",
                "selected_channels": ["email"],
                "consent_basis_type": "public_business_contact_for_manual_outreach",
                "consent_basis_notes": "Synthetic local smoke only.",
            },
        )
        messages = call(client, "GET", f"/v1/outreach-drafts/{package['id']}")["messages"]
        email = next(item for item in messages if item["channel"] == "email")
        log = call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/outreach-log",
            json={
                "outreach_draft_package_id": package["id"],
                "outreach_draft_message_id": email["id"],
                "channel": "email",
                "operator": "smoke-operator",
                "sent_at": datetime.now(UTC).isoformat(),
                "external_reference": "synthetic smoke; no real send",
                "notes": "Operator log only.",
            },
        )
        reply = call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/crm-event",
            json={
                "event_type": "reply_received",
                "channel": "email",
                "operator": "smoke-operator",
                "occurred_at": datetime.now(UTC).isoformat(),
                "summary": "Synthetic reply recorded.",
            },
        )
        meeting = call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/crm-event",
            json={
                "event_type": "meeting_scheduled",
                "channel": "email",
                "operator": "smoke-operator",
                "occurred_at": datetime.now(UTC).isoformat(),
                "summary": "Synthetic meeting recorded.",
            },
        )
        report = call(client, "GET", f"/v1/campaigns/{campaign_id}/reports/pilot", params={"include_details": "true"})
        return {
            "campaign_id": campaign_id,
            "business_id": business_id,
            "score_id": score["id"],
            "brief_id": brief["id"],
            "demo_id": demo["id"],
            "outreach_draft_package_id": package["id"],
            "outreach_log_id": log["id"],
            "crm_event_ids": [reply["id"], meeting["id"]],
            "final_business_state": call(client, "GET", f"/v1/businesses/{business_id}")["state"],
            "report_counts": {item["stage"]: item["count"] for item in report["funnel_metrics"]},
            "system_delivery_count": next(
                item["count"] for item in report["quality_metrics"] if item["code"] == "system_delivery_count"
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
