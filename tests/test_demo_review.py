from fastapi.testclient import TestClient
from lboe_api.main import REVIEW_CHECKLIST, app
from lboe_domain import LeadState


def _checklist(passed: bool = True) -> list[dict[str, object]]:
    return [{"code": code, "label": label, "passed": passed} for code, label in REVIEW_CHECKLIST]


def test_review_approval_and_failed_checklist() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "Review", "vertical": "hair salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "records": [
                    {
                        "display_name": "Review Salon",
                        "category": "hair salon",
                        "locality": "Cape Town",
                        "address_text": "Cape Town",
                        "phone": "+27210000001",
                    }
                ],
            },
        ).json()
        business_id = imported["successes"][0]["business_id"]
        for state in ["DEDUPED", "QUALIFIED", "ENRICHING", "ENRICHED", "AUDITING", "AUDITED"]:
            assert (
                client.post(
                    f"/v1/businesses/{business_id}/transition", json={"to_state": state, "actor": "test"}
                ).status_code
                == 200
            )
        score = client.post(f"/v1/businesses/{business_id}/score", json={"idempotency_key": "review-score"}).json()
        brief = client.post(f"/v1/businesses/{business_id}/brief", json={"idempotency_key": "review-brief"}).json()
        demo = client.post(f"/v1/businesses/{business_id}/demo", json={"idempotency_key": "review-demo"}).json()
        assert score["recommended_next_action"] == "generate_demo"
        assert brief["recommended_action"]["code"] == "generate_demo"
        assert demo["status"] == "qa_passed"
        demo_id = demo["id"]

        failed = _checklist()
        failed[0]["passed"] = False
        negative = client.post(
            f"/v1/demos/{demo_id}/review",
            json={"decision": "approve", "reviewer": "operator", "checklist": failed},
        )
        assert negative.status_code == 409
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == LeadState.REVIEW_PENDING.value

        approved = client.post(
            f"/v1/demos/{demo_id}/review",
            json={
                "decision": "approve",
                "reviewer": "operator",
                "notes": "All checks passed",
                "checklist": _checklist(),
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == LeadState.APPROVED_FOR_OUTREACH.value
        reviews = client.get(f"/v1/demos/{demo_id}/reviews").json()
        assert len(reviews) == 1
        assert reviews[0]["decision"] == "approve"
