"""Conservative Playwright homepage auditor."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path

from lboe_domain import AuditArtifact, AuditEvidence, AuditFinding, AuditRequest, AuditResult, WebsiteResolutionResult
from playwright.async_api import Page, async_playwright

from .resolver import WebsiteResolver


class PlaywrightAuditAdapter:
    def __init__(self, artifact_root: str = "artifacts/audits", max_concurrency: int = 1) -> None:
        self.artifact_root = Path(artifact_root)
        self.semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 2)))
        self.version = "sprint3-playwright-v1"

    async def audit(self, request: AuditRequest) -> AuditResult:
        if not request.website_url:
            return AuditResult(
                website=WebsiteResolutionResult(requested_url="", status="missing"), auditor_version=self.version
            )
        async with self.semaphore:
            resolver = WebsiteResolver(timeout_seconds=request.timeout_seconds)
            resolution = await resolver.resolve(request.website_url)
            findings = [
                AuditFinding(
                    code={
                        "healthy": "WEBSITE_HEALTHY",
                        "http_error": "HTTP_ERROR",
                        "redirect_loop": "REDIRECT_LOOP",
                        "dns_failure": "DNS_FAILURE",
                        "tls_failure": "TLS_FAILURE",
                        "unreachable": "WEBSITE_UNREACHABLE",
                        "blocked": "WEBSITE_INVALID_URL",
                        "missing": "WEBSITE_MISSING",
                    }.get(resolution.status, "WEBSITE_UNREACHABLE"),
                    category="availability",
                    status="detected",
                    severity="info" if resolution.status == "healthy" else "high",
                    source_url=resolution.final_url or resolution.requested_url,
                    observed_value=resolution.status,
                    evidence=[AuditEvidence(kind="resolution", value=resolution.model_dump())],
                    auditor_version=self.version,
                )
            ]
            if resolution.status != "healthy" or not resolution.final_url:
                return AuditResult(website=resolution, findings=findings, auditor_version=self.version)
            return await self._browser_audit(request, resolution, findings)

    async def _browser_audit(
        self, request: AuditRequest, resolution: WebsiteResolutionResult, findings: list[AuditFinding]
    ) -> AuditResult:
        resolution_result = resolution
        final_url = resolution_result.final_url
        assert final_url is not None
        artifacts: list[AuditArtifact] = []
        observed = datetime.now(UTC)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(viewport={"width": 1440, "height": 900})
                page = await context.new_page()
                console_errors: list[str] = []
                failed_requests: list[str] = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on(
                    "requestfailed",
                    lambda req: (
                        failed_requests.append(req.url)
                        if req.resource_type in {"script", "stylesheet", "image", "font"}
                        else None
                    ),
                )
                await page.goto(
                    final_url,
                    wait_until="domcontentloaded",
                    timeout=int(request.timeout_seconds * 1000),
                )
                out = self.artifact_root / str(request.business_id)
                out.mkdir(parents=True, exist_ok=True)
                desktop = out / "desktop-homepage.png"
                await page.screenshot(path=str(desktop), full_page=True)
                artifacts.append(
                    AuditArtifact(
                        kind="desktop_homepage",
                        path=str(desktop),
                        mime_type="image/png",
                        byte_size=desktop.stat().st_size,
                    )
                )
                await self._collect_page_findings(page, final_url, findings, observed, mobile=False)
                await context.close()
                mobile_context = await browser.new_context(viewport={"width": 390, "height": 844})
                mobile = await mobile_context.new_page()
                await mobile.goto(
                    final_url,
                    wait_until="domcontentloaded",
                    timeout=int(request.timeout_seconds * 1000),
                )
                mobile_path = out / "mobile-homepage.png"
                await mobile.screenshot(path=str(mobile_path), full_page=True)
                artifacts.append(
                    AuditArtifact(
                        kind="mobile_homepage",
                        path=str(mobile_path),
                        mime_type="image/png",
                        byte_size=mobile_path.stat().st_size,
                    )
                )
                await self._collect_page_findings(mobile, final_url, findings, observed, mobile=True)
                await mobile_context.close()
                if console_errors:
                    findings.append(
                        AuditFinding(
                            code="BROWSER_CONSOLE_ERRORS",
                            category="technical",
                            status="detected",
                            severity="low",
                            observed_value=len(console_errors),
                            evidence=[AuditEvidence(kind="console", value=console_errors[:10])],
                            source_url=resolution_result.final_url,
                            auditor_version=self.version,
                        )
                    )
                if failed_requests:
                    findings.append(
                        AuditFinding(
                            code="FAILED_FIRST_PARTY_REQUESTS",
                            category="technical",
                            status="detected",
                            severity="low",
                            observed_value=len(failed_requests),
                            evidence=[AuditEvidence(kind="requests", value=failed_requests[:10])],
                            source_url=resolution_result.final_url,
                            auditor_version=self.version,
                        )
                    )
            finally:
                await browser.close()
        return AuditResult(
            website=resolution_result,
            findings=findings,
            artifacts=artifacts,
            technical_metadata={"console_errors": len(console_errors), "failed_requests": len(failed_requests)},
            auditor_version=self.version,
        )

    async def _collect_page_findings(
        self, page: Page, source_url: str, findings: list[AuditFinding], observed: datetime, mobile: bool
    ) -> None:
        title = await page.title()
        meta = await page.locator('meta[name="description"]').count()
        canonical = await page.locator('link[rel="canonical"]').count()
        viewport = await page.locator('meta[name="viewport"]').count()
        h1 = await page.locator("h1").count()
        images = await page.locator("img").all()
        missing_alt = 0
        for image in images:
            if not await image.get_attribute("alt"):
                missing_alt += 1
        text = (await page.locator("body").inner_text()).casefold()
        links = await page.locator("a").all()
        hrefs = [(await link.get_attribute("href") or "") for link in links]

        def add(
            code: str,
            category: str,
            status: str,
            severity: str = "info",
            value: object = None,
            evidence: object = None,
        ) -> None:
            findings.append(
                AuditFinding(
                    code=code,
                    category=category,
                    status=status,
                    severity=severity,
                    observed_value=value,
                    evidence=[
                        AuditEvidence(
                            kind="dom", value=evidence if evidence is not None else value, page_url=source_url
                        )
                    ],
                    source_url=source_url,
                    observed_at=observed,
                    auditor_version=self.version,
                )
            )

        if not mobile:
            add("TITLE_PRESENT", "seo", "detected" if title else "missing", "info" if title else "medium", title)
            add("META_DESCRIPTION_PRESENT", "seo", "detected" if meta else "missing", "info" if meta else "low", meta)
            add(
                "CANONICAL_PRESENT",
                "seo",
                "detected" if canonical else "missing",
                "info" if canonical else "low",
                canonical,
            )
            add(
                "VIEWPORT_META_PRESENT",
                "mobile",
                "detected" if viewport else "missing",
                "info" if viewport else "medium",
                viewport,
            )
            add("H1_PRESENT", "seo", "detected" if h1 else "missing", "info" if h1 else "low", h1)
            add(
                "STRUCTURED_DATA_PRESENT",
                "seo",
                "detected" if await page.locator('script[type="application/ld+json"]').count() else "missing",
                "info",
                await page.locator('script[type="application/ld+json"]').count(),
            )
            add(
                "OPEN_GRAPH_PRESENT",
                "seo",
                "detected" if await page.locator('meta[property^="og:"]').count() else "missing",
                "info",
                await page.locator('meta[property^="og:"]').count(),
            )
            add(
                "IMAGE_ALT_COVERAGE",
                "accessibility",
                "detected",
                "low" if missing_alt else "info",
                {"total": len(images), "missing": missing_alt},
            )
            add(
                "DOCUMENT_LANGUAGE",
                "accessibility",
                "detected" if await page.locator("html[lang]").count() else "missing",
                "info",
                await page.locator("html").get_attribute("lang"),
            )
        if mobile:
            overflow = await page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            add(
                "HORIZONTAL_OVERFLOW",
                "mobile",
                "detected" if overflow else "not_detected",
                "medium" if overflow else "info",
                overflow,
            )
        patterns = {
            "BOOKING_PATH": r"book|reserve|appointment",
            "WHATSAPP_CTA": r"whatsapp|wa\.me",
            "CLICK_TO_CALL": r"tel:",
            "CONTACT_FORM": r"contact|enquir|quote",
            "SERVICE_CATALOGUE": r"service|menu|price|catalog",
            "MAP_LOCATION_LINK": r"maps\.google|google\.com/maps|map",
        }
        for code, pattern in patterns.items():
            matched = bool(re.search(pattern, text)) or any(re.search(pattern, href.casefold()) for href in hrefs)
            add(code, "conversion", "detected" if matched else "not_detected", "info", matched)
