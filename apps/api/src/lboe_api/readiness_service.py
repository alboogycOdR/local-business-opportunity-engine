"""Pure readiness checks for operator-controlled manual outreach."""

from __future__ import annotations

from typing import Any

READINESS_CHANNELS = ("email", "whatsapp", "phone_script", "manual_note")
ALLOWED_DIRECT_BASIS = {
    "existing_relationship",
    "explicit_permission_recorded",
    "public_business_contact_for_manual_outreach",
}


def readiness_checks(
    *,
    package_ready: bool,
    selected_channels_supported: bool,
    selected_messages_exist: bool,
    selected_messages_nonempty: bool,
    draft_safety_checks_passed: bool,
    no_suppression: bool,
    no_do_not_contact_hold: bool,
    no_ambiguous_identity_hold: bool,
    consent_basis_type: str,
    consent_notes: str,
    decision: str,
    reviewer_present: bool,
) -> list[dict[str, Any]]:
    direct = decision == "approve_for_manual_outreach"
    basis_allowed = consent_basis_type in ALLOWED_DIRECT_BASIS if direct else consent_basis_type != "do_not_contact"
    notes_required = (
        not direct
        or consent_basis_type
        not in {"explicit_permission_recorded", "existing_relationship", "public_business_contact_for_manual_outreach"}
        or bool(consent_notes.strip())
    )
    values = {
        "outreach_package_ready": package_ready,
        "selected_channels_supported": selected_channels_supported,
        "selected_messages_exist": selected_messages_exist,
        "selected_messages_nonempty": selected_messages_nonempty,
        "draft_safety_checks_passed": draft_safety_checks_passed,
        "no_suppression": no_suppression,
        "no_do_not_contact_hold": no_do_not_contact_hold,
        "no_ambiguous_identity_hold": no_ambiguous_identity_hold,
        "consent_basis_allowed": basis_allowed,
        "consent_notes_present_when_required": notes_required,
        "no_sending_performed": True,
        "no_contacted_state_transition": True,
        "operator_reviewer_present": reviewer_present,
    }
    return [{"code": code, "passed": passed, "notes": None, "evidence": {}} for code, passed in values.items()]
