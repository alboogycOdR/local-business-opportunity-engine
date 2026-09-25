import asyncio
from uuid import uuid4

import httpx
import pytest
from lboe_domain import CandidateBusiness, DiscoveryRequest, normalize_domain, normalize_phone, normalize_text
from lboe_maps_scraper import MapsScraperAdapter, MapsScraperError


def test_normalization_helpers() -> None:
    assert normalize_text("  Café & Co. ") == "café co"
    assert normalize_phone("+27 (11) 555-1212") == "27115551212"
    assert normalize_phone("123") is None
    assert normalize_domain("https://WWW.Example.com/path") == "example.com"


def test_maps_adapter_normalizes_only_discovery_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/jobs":
            return httpx.Response(201, json={"id": "job-1"})
        if request.url.path == "/api/v1/jobs/job-1":
            return httpx.Response(200, json={"Status": "ok", "secret": "discard"})
        return httpx.Response(
            200, text="title,address,phone,website,review_rating\nCafe,Main St,+2711,https://cafe.example,5\n"
        )

    async def run() -> list[CandidateBusiness]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = MapsScraperAdapter(enabled=True, client=client, poll_interval_seconds=0)
        result = await adapter.discover(DiscoveryRequest(campaign_id=uuid4(), queries=["cafes"], max_results=5))
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result[0].display_name == "Cafe"
    assert result[0].provenance["source_type"] == "scraper"
    assert not hasattr(result[0], "review_rating")


def test_maps_adapter_timeout_and_kill_switch() -> None:
    async def run() -> None:
        adapter = MapsScraperAdapter(enabled=False)
        with pytest.raises(MapsScraperError):
            await adapter.discover(DiscoveryRequest(campaign_id=uuid4(), queries=["cafes"]))

    asyncio.run(run())
