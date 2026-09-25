from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from lboe_api.audit_service import execute_audit
from lboe_api.db import Base, Business, Campaign, PipelineEvent, make_engine
from lboe_domain import AuditFinding, AuditRequest, FakeAuditAdapter
from lboe_website_auditor import SSRFBlocked, WebsiteResolver, validate_public_url
from sqlalchemy.orm import Session


def test_url_normalization_and_ssrf_blocking() -> None:
    assert validate_public_url("https://example.com/path#fragment") == "https://example.com/path"
    with pytest.raises(SSRFBlocked):
        validate_public_url("http://127.0.0.1:8080")
    with pytest.raises(SSRFBlocked):
        validate_public_url("file:///etc/passwd")


def test_redirect_to_private_ip_is_blocked() -> None:
    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        resolver = WebsiteResolver(client=client)
        try:
            result = await resolver.resolve("https://example.com")
            assert result.status == "blocked"
        finally:
            await client.aclose()

    asyncio.run(run())


def test_fake_adapter_is_deterministic() -> None:
    async def run() -> None:
        adapter = FakeAuditAdapter()
        result = await adapter.audit(AuditRequest(business_id=uuid.uuid4(), website_url="https://example.test"))
        assert result.findings[0].code == "WEBSITE_HEALTHY"

    asyncio.run(run())


def test_contract_preserves_evidence_and_classification() -> None:
    finding = AuditFinding(
        code="NO_BOOKING_PATH",
        category="conversion",
        status="detected",
        severity="medium",
        deterministic=True,
        evidence=[],
    )
    assert finding.deterministic is True
    assert finding.auditor_version


def test_http_error_resolution() -> None:
    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        try:
            result = await WebsiteResolver(client=client).resolve("https://example.com")
            assert result.status == "http_error"
        finally:
            await client.aclose()

    asyncio.run(run())


def test_audit_persistence_history_and_lifecycle() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        campaign = Campaign(name="test", vertical="salon")
        session.add(campaign)
        session.flush()
        business = Business(
            campaign_id=campaign.id,
            display_name="Test Salon",
            identity_key="test salon|cape town",
            state="DISCOVERED",
        )
        session.add(business)
        session.commit()
        request = AuditRequest(business_id=business.id, website_url="https://example.test", idempotency_key="one")
        first, _ = asyncio.run(execute_audit(session, FakeAuditAdapter(), business, request))
        second, _ = asyncio.run(
            execute_audit(session, FakeAuditAdapter(), business, request.model_copy(update={"idempotency_key": "two"}))
        )
        assert first.id != second.id
        assert business.state == "AUDITED"
        assert session.query(PipelineEvent).count() == 2
