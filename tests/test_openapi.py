from fastapi.testclient import TestClient
from lboe_api.main import app


def test_openapi_schema_contains_pilot_surface() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in (
        "/v1/campaigns",
        "/v1/campaigns/{campaign_id}/discover",
        "/v1/businesses/{business_id}/audit",
        "/v1/businesses/{business_id}/score",
        "/v1/businesses/{business_id}/brief",
        "/v1/businesses/{business_id}/demo",
        "/v1/demos/{demo_id}/review",
        "/v1/businesses/{business_id}/outreach-draft",
        "/v1/businesses/{business_id}/outreach-readiness",
        "/v1/businesses/{business_id}/outreach-log",
        "/v1/businesses/{business_id}/crm-event",
        "/v1/reports/pilot",
    ):
        assert path in paths
