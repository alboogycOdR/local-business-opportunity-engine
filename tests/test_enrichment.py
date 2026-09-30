import socket
from uuid import uuid4

import httpx
import pytest
from lboe_api.enrichment_service import MAX_HOMEPAGE_BYTES, extract_homepage_facts, fetch_public_html
from lboe_domain import EnrichmentFact, EnrichmentRequest, FakeEnrichmentAdapter
from lboe_website_auditor import SSRFBlocked


def test_homepage_enrichment_extracts_safe_action_facts() -> None:
    business_id = uuid4()
    facts = extract_homepage_facts(
        business_id,
        "https://example.test",
        '<html><body><h1>Salon</h1><p>Hair services</p><a href="/book">Book</a>'
        '<a href="https://wa.me/1">WhatsApp</a><a href="mailto:hello@example.test">Email</a></body></html>',
    )
    assert {item.fact_type for item in facts} >= {
        "website_homepage",
        "booking_link",
        "whatsapp_link",
        "email_address",
        "service_catalogue_present",
    }
    assert all(item.evidence and item.source_type == "business_owned_website" for item in facts)


@pytest.mark.asyncio
async def test_fake_enrichment_is_deterministic() -> None:
    fact = EnrichmentFact(
        business_id=uuid4(),
        source_type="fake",
        fact_type="service_catalogue_present",
        value="true",
        confidence=1,
        observed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    result = await FakeEnrichmentAdapter([fact]).enrich(EnrichmentRequest(business_id=uuid4()))
    assert result.adapter_version == "fake-enrichment-v1"
    assert result.facts[0].business_id != fact.business_id


@pytest.mark.asyncio
async def test_enrichment_fetch_blocks_private_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, **_kwargs: (
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]
            if host == "127.0.0.1"
            else [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        with pytest.raises(SSRFBlocked):
            await fetch_public_html("https://public.example", client)


@pytest.mark.asyncio
async def test_enrichment_fetch_rejects_oversized_html(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda _host, port, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": str(MAX_HOMEPAGE_BYTES + 1)},
            content=b"ignored",
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        assert await fetch_public_html("https://public.example", client) is None
