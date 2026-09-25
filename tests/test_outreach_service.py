from types import SimpleNamespace

from lboe_api.outreach_service import DraftMessage, build_messages, offer_type_for_demo, safety_checks


def test_offer_mapping_and_safe_drafts() -> None:
    assert offer_type_for_demo("starter_website") == "starter_website_offer"
    assert offer_type_for_demo("conversion_upgrade") == "conversion_upgrade_offer"
    business = SimpleNamespace(id="b1", display_name="Concept Salon", category="hair salon")
    demo = SimpleNamespace(id="d1", demo_type="starter_website")
    offer, _angle, _evidence, messages = build_messages(
        business,
        {"id": "brief-1", "opportunities": [{"title": "Starter website opportunity"}]},
        demo,
        ["email", "whatsapp", "phone_script", "manual_note"],
    )
    assert offer == "starter_website_offer"
    assert {message.channel for message in messages} == {"email", "whatsapp", "phone_script", "manual_note"}
    checks = safety_checks(messages, demo_approved=True, suppressed=False, do_not_contact=False, ambiguous=False)
    assert all(check["passed"] for check in checks)
    assert all("ugly" not in message.body.lower() for message in messages)


def test_safety_checks_block_deceptive_copy() -> None:
    message = DraftMessage(
        channel="manual_note",
        body="Act now — your website is ugly and losing customers.",
        subject="Official preview",
        evidence={"source": "test"},
        tone="test",
    )
    checks = safety_checks([message], demo_approved=True, suppressed=False, do_not_contact=False, ambiguous=False)
    result = {check["code"]: check["passed"] for check in checks}
    assert result["no_deceptive_urgency"] is False
    assert result["no_insulting_language"] is False
    assert result["concept_disclaimer_included"] is False
