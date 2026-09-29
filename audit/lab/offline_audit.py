"""Deterministic, network-free audit adapter used by the audit lab and audit tests."""

from __future__ import annotations

import random

from lboe_domain import AuditFinding, AuditRequest, AuditResult, WebsiteResolutionResult


class OfflineAuditAdapter:
    """Deterministic audit results keyed by URL hash; never touches the network."""

    version = "audit-lab-offline-v1"

    async def audit(self, request: AuditRequest) -> AuditResult:
        url = request.website_url
        if not url:
            return AuditResult(
                website=WebsiteResolutionResult(requested_url="", status="missing"), auditor_version=self.version
            )
        rng = random.Random(url)
        status = rng.choices(["healthy", "unreachable", "dns_failure", "http_error"], [70, 12, 10, 8])[0]
        code = {
            "healthy": "WEBSITE_HEALTHY",
            "unreachable": "WEBSITE_UNREACHABLE",
            "dns_failure": "DNS_FAILURE",
            "http_error": "HTTP_ERROR",
        }[status]
        findings = [
            AuditFinding(
                code=code,
                category="availability",
                status="detected",
                severity="info" if status == "healthy" else "high",
                source_url=url,
                observed_value=status,
                auditor_version=self.version,
            )
        ]
        if status == "healthy":
            for detected, p in (
                ("TITLE_PRESENT", 0.9),
                ("META_DESCRIPTION_PRESENT", 0.6),
                ("VIEWPORT_META_PRESENT", 0.8),
                ("H1_PRESENT", 0.7),
                ("BOOKING_PATH", 0.4),
                ("WHATSAPP_CTA", 0.3),
                ("CLICK_TO_CALL", 0.5),
                ("CONTACT_FORM", 0.5),
                ("SERVICE_CATALOGUE", 0.6),
            ):
                findings.append(
                    AuditFinding(
                        code=detected,
                        category="conversion",
                        status="detected" if rng.random() < p else "not_detected",
                        source_url=url,
                        auditor_version=self.version,
                    )
                )
            findings.append(
                AuditFinding(
                    code="IMAGE_ALT_COVERAGE",
                    category="accessibility",
                    status="detected",
                    observed_value={"total": 12, "missing": rng.randint(0, 6)},
                    source_url=url,
                    auditor_version=self.version,
                )
            )
        return AuditResult(
            website=WebsiteResolutionResult(
                requested_url=url,
                normalized_url=url,
                final_url=url if status == "healthy" else None,
                http_status=200 if status == "healthy" else None,
                status=status,
            ),
            findings=findings,
            auditor_version=self.version,
        )
