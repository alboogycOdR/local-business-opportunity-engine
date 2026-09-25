from fastapi.testclient import TestClient
from lboe_api.main import app


def test_health_and_readiness_failure_shape() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").status_code == 503


def test_campaign_import_dedup_provenance_and_transition() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "Pilot", "vertical": "hair_salon"})
        assert campaign.status_code == 201
        campaign_id = campaign.json()["id"]
        payload = {
            "format": "json",
            "records": [
                {"display_name": "Example Salon", "category": "hair_salon", "locality": "Cape Town", "phone": "+2711"},
                {"display_name": "Example Salon", "category": "hair_salon", "locality": "Cape Town"},
                {"display_name": ""},
            ],
        }
        result = client.post(f"/v1/campaigns/{campaign_id}/import", json=payload)
        assert result.json()["imported"] == 1
        assert result.json()["failed"] == 2
        business = client.get("/v1/businesses", params={"campaign_id": campaign_id}).json()[0]
        assert business["provenance"]
        business_id = business["id"]
        assert client.post(f"/v1/businesses/{business_id}/transition", json={"to_state": "DEDUPED"}).status_code == 200
        assert client.post(f"/v1/businesses/{business_id}/transition", json={"to_state": "WON"}).status_code == 409
        suppression = client.post(f"/v1/businesses/{business_id}/suppressions", json={"reason": "do not contact"})
        assert suppression.status_code == 201
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == "SUPPRESSED"


def test_csv_import() -> None:
    with TestClient(app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "CSV", "vertical": "restaurant"}).json()["id"]
        result = client.post(
            f"/v1/campaigns/{campaign_id}/import",
            json={"format": "csv", "csv_text": "display_name,locality\nCafe,Durban\n"},
        )
        assert result.json()["imported"] == 1
