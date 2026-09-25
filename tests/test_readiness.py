from fastapi.testclient import TestClient
from lboe_api.main import REVIEW_CHECKLIST, app


def test_consent_readiness_two_step_workflow() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "Readiness", "vertical": "hair salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "records": [
                    {
                        "display_name": "Readiness Salon",
                        "category": "hair salon",
                        "locality": "Cape Town",
                        "address_text": "Cape Town",
                        "phone": "+27210000002",
                    }
                ],
            },
        ).json()
        business_id = imported["successes"][0]["business_id"]
        for state in ["DEDUPED", "QUALIFIED", "ENRICHING", "ENRICHED", "AUDITING", "AUDITED"]:
            assert client.post(f"/v1/businesses/{business_id}/transition", json={"to_state": state}).status_code == 200
        client.post(f"/v1/businesses/{business_id}/score", json={"idempotency_key": "readiness-score"})
        client.post(f"/v1/businesses/{business_id}/brief", json={"idempotency_key": "readiness-brief"})
        demo = client.post(f"/v1/businesses/{business_id}/demo", json={"idempotency_key": "readiness-demo"}).json()
        checklist = [{"code": code, "label": label, "passed": True} for code, label in REVIEW_CHECKLIST]
        assert (
            client.post(
                f"/v1/demos/{demo['id']}/review",
                json={"decision": "approve", "reviewer": "operator", "checklist": checklist},
            ).status_code
            == 200
        )
        package = client.post(
            f"/v1/businesses/{business_id}/outreach-draft", json={"idempotency_key": "readiness-draft"}
        ).json()
        assert package["status"] == "ready"
        prepared = client.post(
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "prepare_consent_review",
                "reviewer": "operator",
                "consent_basis_type": "manual_operator_review",
            },
        )
        assert prepared.status_code == 200
        assert prepared.json()["resulting_business_state"] == "CONSENT_PENDING"
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == "CONSENT_PENDING"
        negative = client.post(
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "approve_for_manual_outreach",
                "reviewer": "operator",
                "selected_channels": ["email"],
                "consent_basis_type": "unknown",
            },
        )
        assert negative.json()["status"] == "not_outreach_ready_eligible"
        approved = client.post(
            f"/v1/businesses/{business_id}/outreach-readiness",
            json={
                "outreach_draft_package_id": package["id"],
                "decision": "approve_for_manual_outreach",
                "reviewer": "operator",
                "selected_channels": ["email", "phone_script"],
                "consent_basis_type": "public_business_contact_for_manual_outreach",
                "consent_basis_notes": "Operator selected manual channels.",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["resulting_business_state"] == "OUTREACH_READY"
        messages = {
            item["channel"]: item["approved"]
            for item in client.get(f"/v1/outreach-drafts/{package['id']}").json()["messages"]
        }
        assert messages["email"] is True
        assert messages["phone_script"] is True
        assert messages["whatsapp"] is False
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == "OUTREACH_READY"
