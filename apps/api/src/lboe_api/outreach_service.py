"""Deterministic, non-sending outreach draft generation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

VERSION = "outreach-draft-v1"
SUPPORTED_CHANNELS = ("email", "whatsapp", "phone_script", "manual_note")
PROHIBITED = (
    "ugly",
    "losing customers",
    "your website is bad",
    "official preview",
    "act now",
    "limited time",
    "last chance",
    "trusted partner",
    "as discussed",
    "as promised",
)


@dataclass(frozen=True)
class DraftMessage:
    channel: str
    subject: str | None
    body: str
    tone: str
    evidence: dict[str, Any]


def offer_type_for_demo(demo_type: str) -> str:
    return {
        "starter_website": "starter_website_offer",
        "conversion_upgrade": "conversion_upgrade_offer",
        "technical_cleanup_preview": "technical_cleanup_offer",
        "website_refresh": "website_refresh_offer",
    }.get(demo_type, "starter_website_offer")


def build_messages(
    business: Any, brief: dict[str, Any], demo: Any, channels: Sequence[str]
) -> tuple[str, str, dict[str, Any], list[DraftMessage]]:
    name = str(business.display_name)
    category = str(business.category or "local business")
    opportunity = (brief.get("opportunities") or [{}])[0]
    opportunity_title = str(opportunity.get("title") or "a clearer digital presence")
    evidence = {
        "business_id": str(business.id),
        "brief_id": str(brief["id"]),
        "demo_id": str(demo.id),
        "opportunity": opportunity_title,
        "source_type": "business_brief",
    }
    offer_type = offer_type_for_demo(demo.demo_type)
    angle = f"A neutral concept preview addressing {opportunity_title.lower()} for this {category}."
    disclaimer = "This is an independent concept demo, not your official website."
    messages: list[DraftMessage] = []
    if "email" in channels:
        messages.append(
            DraftMessage(
                channel="email",
                subject=f"Independent concept preview for {name}",
                body=(
                    f"Hi {name},\n\nI put together a small concept preview for your {category}. "
                    "It is based on the verified information we have available and focuses on "
                    f"{opportunity_title.lower()}.\n\n"
                    f"{disclaimer}\n\nIf useful, I can customize it with your approved details. "
                    "No pressure — I can send details if this is relevant."
                ),
                tone="polite",
                evidence=evidence,
            )
        )
    if "whatsapp" in channels:
        messages.append(
            DraftMessage(
                channel="whatsapp",
                subject=None,
                body=(
                    f"Hi {name} — I put together an independent concept demo for your {category}. "
                    f"{disclaimer} If useful, may I send the details? No pressure."
                ),
                tone="conversational",
                evidence=evidence,
            )
        )
    if "phone_script" in channels:
        messages.append(
            DraftMessage(
                channel="phone_script",
                subject=None,
                body=(
                    f"Hello, may I speak with someone responsible for {name}? "
                    "I have an independent concept preview based on publicly available business details. "
                    "It is not your official website. May I send the details for review?"
                ),
                tone="permission-seeking",
                evidence=evidence,
            )
        )
    if "manual_note" in channels:
        messages.append(
            DraftMessage(
                channel="manual_note",
                subject=None,
                body=(
                    f"Approved concept demo for {name}. Offer angle: {angle} "
                    "Confirm consent and channel preference before any future contact."
                ),
                tone="operator",
                evidence=evidence,
            )
        )
    return offer_type, angle, evidence, messages


def safety_checks(
    messages: list[DraftMessage],
    *,
    demo_approved: bool,
    suppressed: bool,
    do_not_contact: bool,
    ambiguous: bool,
    preview_internal: bool = True,
) -> list[dict[str, Any]]:
    text = "\n".join(message.body + "\n" + (message.subject or "") for message in messages).lower()
    checks = {
        "no_sending_performed": True,
        "demo_approved": demo_approved,
        "concept_disclaimer_included": "independent concept" in text and "not your official website" in text,
        "no_official_site_claim": not re.search(r"(?<!not your )official website", text),
        "no_fake_testimonials": "testimonial" not in text and "review quote" not in text,
        "no_fake_prices": not re.search(r"(?:\$|r)\s?\d+", text),
        "no_unsupported_awards": "award" not in text and "best" not in text,
        "no_deceptive_urgency": not any(phrase in text for phrase in ("act now", "limited time", "last chance")),
        "no_insulting_language": not any(phrase in text for phrase in PROHIBITED),
        "evidence_backed_opportunity": all(bool(message.evidence) for message in messages),
        "suppression_not_present": not suppressed,
        "do_not_contact_not_present": not do_not_contact,
        "ambiguous_identity_not_present": not ambiguous,
        "preview_reference_internal": preview_internal,
        "no_raw_personal_data_overuse": not any(
            token in text for token in ("email address", "phone number", "personal data")
        ),
    }
    return [{"code": code, "passed": passed, "notes": None, "evidence": {}} for code, passed in checks.items()]
