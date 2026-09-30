"""Small, deterministic homepage enrichment; no broad crawl or raw payload storage."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import urljoin
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from lboe_domain import EnrichmentEvidence, EnrichmentFact, EnrichmentRequest, EnrichmentResult
from lboe_website_auditor import SSRFBlocked, validate_public_url
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Business, Contact, EnrichmentFactRow, EnrichmentRun

VERSION = "homepage-enrichment-v1"
MAX_HOMEPAGE_BYTES = 2_000_000
MAX_REDIRECTS = 8


def enrichment_idempotency_key(request: EnrichmentRequest) -> str:
    material = {
        "business_id": str(request.business_id),
        "website_url": request.website_url,
        "caller_key": request.idempotency_key,
    }
    return "enrich:" + hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


async def fetch_public_html(url: str, client: httpx.AsyncClient | None = None) -> tuple[str, str] | None:
    """Fetch one bounded public HTML document, validating every redirect hop."""
    current = validate_public_url(url)
    visited = {current}
    owned_client = client is None
    active_client = client or httpx.AsyncClient(timeout=15, follow_redirects=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            async with active_client.stream("GET", current, headers={"User-Agent": "LBOE enrichment/1.0"}) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        return None
                    target = validate_public_url(urljoin(current, location))
                    if target in visited:
                        return None
                    visited.add(target)
                    current = target
                    continue
                if not response.is_success or "text/html" not in response.headers.get("content-type", ""):
                    return None
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_HOMEPAGE_BYTES:
                    return None
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_HOMEPAGE_BYTES:
                        return None
                encoding = response.encoding or "utf-8"
                return current, bytes(body).decode(encoding, errors="replace")
        return None
    finally:
        if owned_client:
            await active_client.aclose()


def extract_homepage_facts(business_id: UUID, url: str, html: str) -> list[EnrichmentFact]:
    now = datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    facts: list[EnrichmentFact] = []

    def evidence(locator: str, excerpt: str | None = None) -> list[EnrichmentEvidence]:
        return [EnrichmentEvidence(source_url=url, locator=locator, excerpt=excerpt, observed_at=now)]

    facts.append(
        EnrichmentFact(
            business_id=business_id,
            source_type="business_owned_website",
            source_url=url,
            fact_type="website_homepage",
            value=url,
            confidence=0.95,
            observed_at=now,
            evidence=evidence("document"),
        )
    )
    links = [str(a.get("href") or "").strip() for a in soup.find_all("a")]
    text = soup.get_text(" ", strip=True)
    lower = text.casefold()
    for href in links:
        link = href.casefold()
        if "book" in link or "reserv" in link or "fresha" in link:
            facts.append(
                EnrichmentFact(
                    business_id=business_id,
                    source_type="business_owned_website",
                    source_url=url,
                    fact_type="booking_link",
                    value=href[:500],
                    confidence=0.9,
                    observed_at=now,
                    evidence=evidence("a[href]", href[:200]),
                )
            )
        if "wa.me" in link or "whatsapp" in link:
            facts.append(
                EnrichmentFact(
                    business_id=business_id,
                    source_type="business_owned_website",
                    source_url=url,
                    fact_type="whatsapp_link",
                    value=href[:500],
                    confidence=0.9,
                    observed_at=now,
                    evidence=evidence("a[href]", href[:200]),
                )
            )
        if link.startswith("mailto:"):
            facts.append(
                EnrichmentFact(
                    business_id=business_id,
                    source_type="business_owned_website",
                    source_url=url,
                    fact_type="email_address",
                    value=href[7:507],
                    confidence=0.9,
                    observed_at=now,
                    evidence=evidence("a[href]", href[:200]),
                )
            )
        if link.startswith("tel:"):
            facts.append(
                EnrichmentFact(
                    business_id=business_id,
                    source_type="business_owned_website",
                    source_url=url,
                    fact_type="phone_number",
                    value=href[4:504],
                    confidence=0.9,
                    observed_at=now,
                    evidence=evidence("a[href]", href[:200]),
                )
            )
        if any(host in link for host in ("instagram.com", "facebook.com", "tiktok.com")):
            facts.append(
                EnrichmentFact(
                    business_id=business_id,
                    source_type="public_social",
                    source_url=url,
                    fact_type="social_link",
                    value=href[:500],
                    confidence=0.7,
                    observed_at=now,
                    evidence=evidence("a[href]", href[:200]),
                    policy="operator_review",
                )
            )
    if any(word in lower for word in ("services", "hair", "salon", "treatment", "styling")):
        facts.append(
            EnrichmentFact(
                business_id=business_id,
                source_type="business_owned_website",
                source_url=url,
                fact_type="service_catalogue_present",
                value="true",
                confidence=0.8,
                observed_at=now,
                evidence=evidence("body", text[:200]),
            )
        )
    if any(word in lower for word in ("price", "pricing", "r", "$", "book now")):
        facts.append(
            EnrichmentFact(
                business_id=business_id,
                source_type="business_owned_website",
                source_url=url,
                fact_type="price_list_present",
                value="true",
                confidence=0.65,
                observed_at=now,
                evidence=evidence("body", text[:200]),
            )
        )
    return facts


async def execute_enrichment(session: Session, request: EnrichmentRequest) -> tuple[EnrichmentRun, EnrichmentResult]:
    business = session.get(Business, request.business_id)
    if business is None:
        raise ValueError("business_not_found")
    website_contact = session.scalar(
        select(Contact).where(Contact.business_id == business.id, Contact.channel == "website")
    )
    url = request.website_url or (website_contact.value if website_contact else None)
    now = datetime.now(UTC)
    run = EnrichmentRun(
        business_id=business.id,
        source_type="business_owned_website",
        status="succeeded",
        started_at=now,
        completed_at=now,
        adapter_version=VERSION,
    )
    session.add(run)
    session.flush()
    facts: list[EnrichmentFact] = []
    if url and re.match(r"^https?://", url, re.I):
        try:
            document = await fetch_public_html(url)
            if document is not None:
                final_url, html = document
                facts = extract_homepage_facts(request.business_id, final_url, html)
            else:
                run.status = "completed_with_warnings"
        except (httpx.HTTPError, UnicodeError, SSRFBlocked, ValueError):
            run.status = "completed_with_warnings"
    for fact in facts:
        session.add(
            EnrichmentFactRow(
                enrichment_run_id=run.id,
                business_id=fact.business_id,
                source_type=fact.source_type,
                source_url=fact.source_url,
                fact_type=fact.fact_type,
                value=fact.value,
                confidence=fact.confidence,
                observed_at=fact.observed_at,
                evidence={"items": [item.model_dump(mode="json") for item in fact.evidence]},
                policy=fact.policy,
            )
        )
    session.commit()
    session.refresh(run)
    return run, EnrichmentResult(facts=facts, adapter_version=VERSION, status=run.status)
