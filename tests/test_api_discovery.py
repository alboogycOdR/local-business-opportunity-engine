from fastapi.testclient import TestClient
from lboe_api.main import app, set_discovery_adapter
from lboe_domain import CandidateBusiness, FakeDiscoveryAdapter


def test_discovery_fake_dedupe_and_idempotency() -> None:
    fake = FakeDiscoveryAdapter(
        [
            CandidateBusiness(
                source="fake",
                source_id="a",
                display_name="Cafe One",
                locality="Durban",
                phone="+27115551212",
                website="https://cafe.example",
            ),
            CandidateBusiness(
                source="fake",
                source_id="a",
                display_name="Cafe One Again",
                locality="Durban",
                phone="+27115551212",
                website="https://cafe.example",
            ),
        ]
    )
    set_discovery_adapter(fake)
    with TestClient(app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "Discovery", "vertical": "restaurant"}).json()["id"]
        body = {"queries": ["cafes"], "idempotency_key": "test-discovery-1"}
        first = client.post(f"/v1/campaigns/{campaign_id}/discover", json=body)
        assert first.status_code == 200
        assert first.json()["result"]["imported"] == 1
        assert first.json()["result"]["duplicates"] == 1
        second = client.post(f"/v1/campaigns/{campaign_id}/discover", json=body)
        assert second.json()["job_id"] == first.json()["job_id"]
        assert fake.calls == 1
        business = client.get("/v1/businesses", params={"campaign_id": campaign_id}).json()[0]
        assert len(business["provenance"]) >= 1


def test_caller_key_is_campaign_scoped() -> None:
    fake = FakeDiscoveryAdapter(
        [CandidateBusiness(source="fake", source_id="one", display_name="Cafe", locality="Cape Town")]
    )
    set_discovery_adapter(fake)
    with TestClient(app) as client:
        campaign_a = client.post("/v1/campaigns", json={"name": "A", "vertical": "restaurant"}).json()["id"]
        campaign_b = client.post("/v1/campaigns", json={"name": "B", "vertical": "restaurant"}).json()["id"]
        body = {"queries": ["cafes"], "idempotency_key": "pilot-1"}
        job_a = client.post(f"/v1/campaigns/{campaign_a}/discover", json=body).json()["job_id"]
        job_b = client.post(f"/v1/campaigns/{campaign_b}/discover", json=body).json()["job_id"]
        assert job_a != job_b
        assert fake.calls == 2


def test_ambiguous_candidates_are_not_merged() -> None:
    fake = FakeDiscoveryAdapter(
        [
            CandidateBusiness(
                source="fake", source_id="a", display_name="Shop A", locality="Durban", phone="+27115550000"
            ),
            CandidateBusiness(
                source="fake", source_id="b", display_name="Shop B", locality="Durban", website="https://shop.example"
            ),
        ]
    )
    set_discovery_adapter(fake)
    with TestClient(app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "Ambiguous", "vertical": "retail"}).json()["id"]
        client.post(f"/v1/campaigns/{campaign_id}/discover", json={"queries": ["shops"]})
        # Two independent signals point to two different existing records.
        fake.candidates = [
            CandidateBusiness(
                source="fake",
                source_id="new-2",
                display_name="Shop C",
                locality="Durban",
                phone="+27115550000",
                website="https://shop.example",
            )
        ]
        result = client.post(
            f"/v1/campaigns/{campaign_id}/discover", json={"queries": ["shops"], "idempotency_key": "ambiguous-2"}
        )
        assert result.status_code == 200
        assert result.json()["result"]["ambiguous"] == 1
        unresolved = client.get(f"/v1/campaigns/{campaign_id}/discovery-candidates", params={"status": "ambiguous"})
        assert unresolved.status_code == 200
        assert unresolved.json()[0]["normalized_payload"]["display_name"] == "Shop C"
        assert unresolved.json()[0]["dedupe_evidence"]["conflicting_business_ids"]


def test_phone_and_domain_matches_are_conservative_exact_dedupes() -> None:
    fake = FakeDiscoveryAdapter(
        [
            CandidateBusiness(
                source="fake", source_id="phone-1", display_name="Phone Shop", locality="Pretoria", phone="+27115551234"
            ),
            CandidateBusiness(
                source="fake",
                source_id="domain-1",
                display_name="Domain Shop",
                locality="Pretoria",
                website="https://domain.example",
            ),
        ]
    )
    set_discovery_adapter(fake)
    with TestClient(app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "Signals", "vertical": "retail"}).json()["id"]
        client.post(f"/v1/campaigns/{campaign_id}/discover", json={"queries": ["shops"]})
        fake.candidates = [
            CandidateBusiness(
                source="other", source_id="phone-2", display_name="Renamed", locality="Pretoria", phone="27115551234"
            ),
            CandidateBusiness(
                source="other",
                source_id="domain-2",
                display_name="Renamed",
                locality="Pretoria",
                website="domain.example",
            ),
        ]
        response = client.post(
            f"/v1/campaigns/{campaign_id}/discover", json={"queries": ["shops"], "idempotency_key": "signals-2"}
        )
        assert response.json()["result"]["duplicates"] == 2


def test_cross_provider_merge_attaches_external_identity() -> None:
    fake = FakeDiscoveryAdapter(
        [
            CandidateBusiness(source="manual", display_name="Salon", locality="Cape Town", phone="+27215551234"),
        ]
    )
    set_discovery_adapter(fake)
    with TestClient(app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "External", "vertical": "salon"}).json()["id"]
        client.post(f"/v1/campaigns/{campaign_id}/discover", json={"queries": ["salons"]})
        fake.candidates = [
            CandidateBusiness(
                source="maps_scraper",
                source_id="maps-123",
                display_name="Salon Renamed",
                locality="Cape Town",
                phone="27215551234",
            ),
        ]
        client.post(
            f"/v1/campaigns/{campaign_id}/discover", json={"queries": ["salons"], "idempotency_key": "external-2"}
        )
        business = client.get("/v1/businesses", params={"campaign_id": campaign_id}).json()[0]
        assert {item["source_id"] for item in business["external_identities"]} == {"maps-123"}
