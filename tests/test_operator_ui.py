from fastapi.testclient import TestClient
from lboe_api.main import app


def test_operator_ui_pages_and_safety_banner() -> None:
    with TestClient(app) as client:
        campaign = client.post(
            "/v1/campaigns", json={"name": "UI Pilot", "vertical": "hair_salon", "geography": "Cape Town"}
        ).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "UI Salon", "category": "hair salon"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        for path in (
            "/ui",
            "/ui/campaigns",
            f"/ui/campaigns/{campaign['id']}",
            f"/ui/businesses/{business_id}",
            "/ui/reports/pilot",
            f"/ui/campaigns/{campaign['id']}/reports/pilot",
            "/ui/queues",
            "/ui/queues/demo-review",
            "/ui/operators",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "System delivery is disabled" in response.text


def test_ui_suppression_is_audited() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "UI Safety", "vertical": "salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "Suppression UI", "category": "salon"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        response = client.post(
            f"/ui/businesses/{business_id}/suppress", data={"reason": "UI test"}, follow_redirects=False
        )
        assert response.status_code == 303
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == "SUPPRESSED"
