"""Deterministic, template-first concept demo generation and QA."""

from __future__ import annotations

import html
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lboe_domain import DemoClaim, DemoSection

VERSION = "demo-v1"
PROHIBITED = (
    "best salon",
    "leading salon",
    "top rated",
    "trusted by thousands",
    "5-star",
    "5 star",
    "client testimonial",
    "customer testimonial",
    "special offer",
)

QA_GUIDANCE = {
    "concept_banner_present": ("critical", "Restore the independent concept disclaimer.", "regenerate"),
    "business_name_present": ("critical", "Verify the business name against the brief.", "manual_edit"),
    "prohibited_phrases_absent": ("critical", "Remove unsupported or deceptive marketing language.", "manual_edit"),
    "official_site_claim_absent": ("critical", "Remove any implication that this is the official site.", "manual_edit"),
    "no_fake_testimonials": ("critical", "Remove testimonials or review-like claims.", "manual_edit"),
    "no_fake_prices": ("critical", "Remove prices unless explicitly verified.", "manual_edit"),
    "claims_have_evidence": (
        "high",
        "Map each verified claim to stored evidence or mark it generic/placeholder.",
        "manual_edit",
    ),
    "html_exists": ("critical", "Regenerate missing HTML artifacts.", "regenerate"),
    "css_exists": ("high", "Regenerate missing CSS artifact.", "regenerate"),
    "metadata_exists": ("medium", "Regenerate missing metadata artifact.", "regenerate"),
    "no_external_forms": ("critical", "Remove external submission forms; use safe placeholders.", "manual_edit"),
    "no_external_tracking": ("critical", "Remove scripts and tracking from the concept preview.", "manual_edit"),
}


@dataclass(frozen=True)
class RenderedDemo:
    html: str
    css: str
    metadata: dict[str, Any]
    sections: list[DemoSection]
    claims: list[DemoClaim]
    # Verified business facts rendered verbatim. QA rules about *generated* marketing copy
    # (prices, superlatives, testimonials) must not fire on the business's own name/address.
    verified_values: tuple[str, ...] = ()


def _fact(facts: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    return next((item for item in facts if item.get("label") == label), None)


def _anchor(section_type: str) -> str:
    return section_type.replace("_", "-")


def render_demo(
    demo_id: uuid.UUID,
    business: Any,
    brief: dict[str, Any],
    demo_type: str,
) -> RenderedDemo:
    facts = [fact for values in brief.get("facts", {}).values() for fact in values]
    name = str(business.display_name)
    category = str(business.category or "local business")
    # Briefs label the address "Address/locality"; accept the legacy "address" label too.
    address_fact = _fact(facts, "Address/locality") or _fact(facts, "address")
    if address_fact is not None and not address_fact.get("value"):
        address_fact = None
    phone_fact = _fact(facts, "phone")
    location = str(address_fact["value"]) if address_fact else (business.locality or "your local area")
    phone = str(phone_fact["value"]) if phone_fact else ""
    contact_text = (
        f"Call {phone} when confirmed." if phone else "Contact details can be added after operator verification."
    )
    evidence = {"source_type": "business_brief", "brief_id": str(brief["id"])}
    sections = [
        DemoSection(
            section_type="concept_banner",
            heading="Independent concept preview",
            body="Concept preview prepared independently for demonstration. Not the official website of this business.",
            sort_order=0,
            evidence={"claim_type": "generic"},
        ),
        DemoSection(
            section_type="hero",
            heading=name,
            body=f"A mobile-friendly {category.lower()} website concept for clear local discovery.",
            sort_order=1,
            evidence=evidence,
        ),
        DemoSection(
            section_type="primary_cta",
            heading="Make the next step simple",
            body="Add online booking or WhatsApp enquiry flow when the business owner confirms the preferred route.",
            sort_order=2,
            evidence={"claim_type": "generic", "placeholder": True},
        ),
        DemoSection(
            section_type="services",
            heading="Services and capabilities",
            body="Service information can be customized with the business owner.",
            sort_order=3,
            evidence={"claim_type": "placeholder", "source": "operator_review"},
        ),
        DemoSection(
            section_type="trust_safe",
            heading="A clear local presence",
            body="Present verified business information and practical contact options in one easy-to-scan place.",
            sort_order=4,
            evidence={"claim_type": "generic"},
        ),
        DemoSection(
            section_type="location_contact",
            heading="Location and contact",
            body=f"{location}. {contact_text}",
            sort_order=5,
            evidence=evidence if address_fact or phone_fact else {"claim_type": "placeholder"},
        ),
        DemoSection(
            section_type="footer",
            heading="Independent concept preview",
            body="Prepared independently for demonstration. Not the official website of this business.",
            sort_order=6,
            evidence={"claim_type": "generic"},
        ),
    ]
    claims = [
        DemoClaim(claim_text=name, claim_type="verified", evidence=evidence, confidence=1.0),
        DemoClaim(claim_text=category, claim_type="verified", evidence=evidence, confidence=0.9),
        DemoClaim(
            claim_text="Service information can be customized with the business owner.",
            claim_type="placeholder",
            evidence={"claim_type": "placeholder"},
            confidence=1.0,
        ),
        DemoClaim(
            claim_text="Mobile-friendly salon website concept.",
            claim_type="generic",
            evidence={"claim_type": "generic"},
            confidence=1.0,
        ),
    ]
    section_html = "\n".join(
        f'<section class="{html.escape(section.section_type)}" id="{html.escape(_anchor(section.section_type))}">'
        f"<h2>{html.escape(section.heading)}</h2><p>{html.escape(section.body)}</p></section>"
        for section in sections
    )
    page_title = f"{html.escape(name)} — concept preview"
    css = (
        ":root{font-family:system-ui,sans-serif;color:#17202a;background:#f8f5f0}"
        "body{margin:0}main{max-width:960px;margin:auto;padding:2rem}"
        "section,header,footer{background:#fff;padding:1.5rem;margin:1rem 0;border-radius:1rem}"
        "a{display:inline-block;margin:.25rem;padding:.65rem 1rem;border:1px solid #52616b;"
        "border-radius:999px;color:#17202a}"
        ".eyebrow{letter-spacing:.08em;text-transform:uppercase;font-size:.8rem}"
        ".concept_banner,.concept-banner{background:#fff4cc;border:2px solid #8a6d00}"
        "@media(max-width:600px){main{padding:1rem}h1{font-size:2rem}a{display:block;text-align:center}}"
    )
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{page_title}</title><style>{css}</style></head>"
        f'<body><main><header><p class="eyebrow">Independent concept preview</p>'
        f"<h1>{html.escape(name)}</h1><p>{html.escape(category)} concept for {html.escape(location)}.</p>"
        '<nav aria-label="Concept sections"><a href="#primary-cta">Booking or WhatsApp (to be confirmed)</a> '
        '<a href="#location-contact">Location and contact</a></nav></header>'
        f"{section_html}<footer><p>Concept preview prepared independently for demonstration. "
        "Not the official website of this business.</p></footer></main></body></html>"
    )
    return RenderedDemo(
        html=page,
        css=css,
        metadata={"demo_id": str(demo_id), "version": VERSION, "demo_type": demo_type, "business_id": str(business.id)},
        sections=sections,
        claims=claims,
        verified_values=tuple(value for value in (name, category, location, phone) if value),
    )


def write_artifacts(root: Path, demo_id: uuid.UUID, rendered: RenderedDemo) -> list[dict[str, Any]]:
    directory = root / "demos" / str(demo_id)
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "index.html": (rendered.html, "text/html"),
        "styles.css": (rendered.css, "text/css"),
        "metadata.json": (json.dumps(rendered.metadata, indent=2), "application/json"),
    }
    artifacts: list[dict[str, Any]] = []
    for filename, (content, mime) in files.items():
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        artifacts.append(
            {"kind": filename.rsplit(".", 1)[0], "path": str(path), "mime_type": mime, "byte_size": path.stat().st_size}
        )
    return artifacts


def qa_demo(root: Path, demo_id: uuid.UUID, rendered: RenderedDemo) -> tuple[str, dict[str, bool]]:
    directory = root / "demos" / str(demo_id)
    content = (directory / "index.html").read_text(encoding="utf-8")
    # Compare against the text a visitor sees (entities decoded), so "&" and "'" in a
    # business name no longer fail the name check.
    lowered = html.unescape(re.sub(r"<style>.*?</style>", " ", content, flags=re.S)).lower()
    # Copy rules target LBOE-generated marketing text. Verified facts (name, category,
    # address, phone) are the business's own words and are removed before those rules run,
    # otherwise "Hair 2 Go", "Floor 1" or "concept for 12 Kloof Street" read as prices.
    generated = lowered
    for value in sorted(rendered.verified_values, key=len, reverse=True):
        generated = generated.replace(value.lower(), " ")
    checks: dict[str, bool] = {
        "concept_banner_present": "concept preview prepared independently" in lowered,
        "business_name_present": bool(rendered.claims and rendered.claims[0].claim_text.lower() in lowered),
        "prohibited_phrases_absent": not any(phrase in generated for phrase in PROHIBITED),
        "official_site_claim_absent": not re.search(r"(?<!not the )official website", generated),
        "no_fake_testimonials": "testimonial" not in generated and "review quote" not in generated,
        "no_fake_prices": not re.search(r"(?:\$|\br)\s?\d+", generated),
        "claims_have_evidence": all(
            claim.evidence or claim.claim_type in {"generic", "placeholder"} for claim in rendered.claims
        ),
        "html_exists": (directory / "index.html").is_file(),
        "css_exists": (directory / "styles.css").is_file(),
        "metadata_exists": (directory / "metadata.json").is_file(),
        # Markup checks run on the raw HTML: an escaped "<script>" in a name is text, not a tag.
        "no_external_forms": "<form" not in content.lower(),
        "no_external_tracking": "<script" not in content.lower(),
    }
    return ("passed" if all(checks.values()) else "failed", checks)


def qa_explanations(checks: dict[str, bool]) -> list[dict[str, str | bool]]:
    return [
        {
            "code": code,
            "passed": passed,
            "severity": QA_GUIDANCE.get(code, ("medium", "Inspect this QA check.", "manual_edit"))[0],
            "explanation": QA_GUIDANCE.get(code, ("medium", "Inspect this QA check.", "manual_edit"))[1],
            "recommended_action": QA_GUIDANCE.get(code, ("medium", "Inspect this QA check.", "manual_edit"))[2],
            "sharing_blocked": not passed,
        }
        for code, passed in checks.items()
    ]
