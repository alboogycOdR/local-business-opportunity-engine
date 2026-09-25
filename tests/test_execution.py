from datetime import UTC, datetime

from fastapi.testclient import TestClient
from lboe_api.main import REVIEW_CHECKLIST, app


def test_manual_execution_log_and_duplicate_guard() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "Execution", "vertical": "hair salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "records": [
                    {
                        "display_name": "Execution Salon",
                        "category": "hair salon",
                        "locality": "Cape Town",
                        "phone": "+27210000003",
                    }
                ],
            },
        ).json()
        business_id = imported["successes"][0]["business_id"]
        for state in ["DEDUPED", "QUALIFIED", "ENRICHING", "ENRICHED", "AUDITING", "AUDITED"]:
            assert client.post(f"/v1/businesses/{business_id}/transition", json={"to_state": state}).status_code == 200
        client.post(f"/v1/businesses/{business_id}/score", json={"idempotency_key": "execution-score"})
        client.post(f"/v1/businesses/{business_id}/brief", json={"idempotency_key": "execution-brief"})
        demo = client.post(f"/v1/businesses/{business_id}/demo", json={"idempotency_key": "execution-demo"}).json()
        checklist = [{"code": code, "label": label, "passed": True} for code, label in REVIEW_CHECKLIST]
        client.post(
            f"/v1/demos/{demo['id']}/review",
            json={"decision": "approve", "reviewer": "operator", "checklist": checklist},
        )
        package = client.post(
            f"/v1/businesses/{business_id}/outreach-draft", json={"idempotency_key": "execution-draft"}
        ).json()
        client.post(
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "prepare_consent_review",
                "reviewer": "operator",
                "consent_basis_type": "manual_operator_review",
            },
        )
        client.post(
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "approve_for_manual_outreach",
                "reviewer": "operator",
                "selected_channels": ["email"],
                "consent_basis_type": "public_business_contact_for_manual_outreach",
                "consent_basis_notes": "Manual channel selected.",
            },
        )
        messages = client.get(f"/v1/outreach-drafts/{package['id']}").json()["messages"]
        email = next(item for item in messages if item["channel"] == "email")
        whatsapp = next(item for item in messages if item["channel"] == "whatsapp")
        negative = client.post(
            f"/v1/businesses/{business_id}/outreach-log",
            json={
                "outreach_draft_package_id": package["id"],
                "outreach_draft_message_id": whatsapp["id"],
                "channel": "whatsapp",
                "operator": "operator",
                "sent_at": datetime.now(UTC).isoformat(),
            },
        )
        assert negative.json()["status"] == "not_manual_outreach_log_eligible"
        assert negative.json()["reason"] == "draft_message_not_approved"
        result = client.post(
            f"/v1/businesses/{business_id}/outreach-log",
            json={
                "outreach_draft_package_id": package["id"],
                "outreach_draft_message_id": email["id"],
                "channel": "email",
                "operator": "operator",
                "sent_at": datetime.now(UTC).isoformat(),
                "external_reference": "test only",
                "notes": "Recorded without system delivery.",
            },
        )
        assert result.status_code == 200
        assert result.json()["delivery_performed_by_system"] is False
        assert result.json()["resulting_business_state"] == "CONTACTED"
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == "CONTACTED"
        duplicate = client.post(
            f"/v1/businesses/{business_id}/outreach-log",
            json={
                "outreach_draft_package_id": package["id"],
                "outreach_draft_message_id": email["id"],
                "channel": "email",
                "operator": "operator",
                "sent_at": datetime.now(UTC).isoformat(),
                "idempotency_key": "second-send",
            },
        )
        assert duplicate.json()["status"] == "not_manual_outreach_log_eligible"
        assert duplicate.json()["reason"] == "business_not_outreach_ready"
