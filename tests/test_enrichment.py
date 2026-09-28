from uuid import uuid4

import pytest
from lboe_api.enrichment_service import extract_homepage_facts
from lboe_domain import EnrichmentFact, EnrichmentRequest, FakeEnrichmentAdapter


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
