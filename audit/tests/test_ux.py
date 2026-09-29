"""WS-O regression tests: workflow completeness, safety legibility, content and accessibility."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup
from conftest import TARGET

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _soup(client: Any, path: str) -> BeautifulSoup:
    response = client.get(path)
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text[:200]}"
    return BeautifulSoup(response.text, "html.parser")


def _no_website_demo(seed: Any, **overrides: Any) -> tuple[str, dict[str, Any]]:
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1, **overrides)
    return business_id, seed.demo(business_id)


# --- Workflow completeness ------------------------------------------------------------------


def test_LBOE_AUD_110_demo_awaiting_review_can_be_approved_from_the_ui(client: Any, seed: Any) -> None:
    """The human-review gate has an API but no UI: operators stall at REVIEW_PENDING."""
    business_id, demo = _no_website_demo(seed)
    assert demo["status"] == "qa_passed", demo
    pages = [f"/ui/businesses/{business_id}", f"/ui/demos/{demo['id']}/qa", f"/ui/demos/{demo['id']}/preview-links"]
    review_forms = [
        form
        for path in pages
        for form in _soup(client, path).find_all("form")
        if re.search(r"/demos/[^/]+/review$", form.get("action") or "") and form.get("method", "").lower() == "post"
    ]
    assert review_forms, "no UI form submits a demo review decision (approve/reject/request changes)"


def _submit(client: Any, path: str, action_pattern: str, choices: dict[str, Any]) -> Any:
    """Submit the first form on ``path`` whose action matches, like a browser would.

    Hidden/default values are kept; ``choices`` sets text fields, picks radio/select
    values, and ticks checkboxes (``True`` ticks every box with that name).
    """
    soup = _soup(client, path)
    form = next(
        (f for f in soup.find_all("form") if re.search(action_pattern, f.get("action") or "")),
        None,
    )
    assert form is not None, f"{path}: no form posting to {action_pattern}"
    data: list[tuple[str, str]] = []
    for field in form.find_all(["input", "select", "textarea"]):
        name = field.get("name")
        if not name:
            continue
        kind = (field.get("type") or "").lower()
        wanted = choices.get(name)
        if kind == "checkbox":
            if wanted is True or (isinstance(wanted, list) and field.get("value") in wanted):
                data.append((name, field.get("value", "on")))
        elif kind == "radio":
            if wanted == field.get("value"):
                data.append((name, field["value"]))
        elif field.name == "select":
            options = [o.get("value") for o in field.find_all("option") if o.get("value")]
            data.append((name, str(wanted) if wanted is not None else options[0]))
        else:
            data.append((name, str(wanted) if wanted is not None else (field.get("value") or field.text or "")))
    payload: dict[str, list[str]] = {}
    for name, value in data:
        payload.setdefault(name, []).append(value)
    response = client.post(form["action"], data=payload, follow_redirects=False)
    assert response.status_code in {302, 303}, response.text[:300]
    location = response.headers["location"]
    assert "action_error" not in location, f"{form['action']} refused: {location}"
    return location


def _state(client: Any, business_id: str) -> str:
    return str(client.get(f"/v1/businesses/{business_id}").json()["state"])


def test_LBOE_AUD_110_golden_path_completes_through_ui_forms(client: Any, seed: Any) -> None:
    """From a QA-passed concept to a recorded reply using only operator-console forms.

    Baseline: none of these forms exist, so an operator stalls at REVIEW_PENDING.
    """
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    demo = seed.demo(business_id)
    assert demo["status"] == "qa_passed" and _state(client, business_id) == "REVIEW_PENDING"
    page = f"/ui/businesses/{business_id}"
    _submit(client, page, r"/demos/[^/]+/review$", {"checklist": True, "decision": "approve", "reviewer": "Ops"})
    assert _state(client, business_id) == "APPROVED_FOR_OUTREACH"
    _submit(client, page, r"/outreach-draft$", {"channels": ["email"]})
    _submit(client, page, r"/outreach-readiness$", {"reviewer": "Ops"})
    assert _state(client, business_id) == "CONSENT_PENDING"
    _submit(
        client,
        page,
        r"/outreach-readiness$",
        {
            "consent_basis_type": "explicit_permission_recorded",
            "consent_basis_notes": "Owner asked for a concept at the 2 Oct market stall",
            "selected_channels": ["email"],
            "decision": "approve_for_manual_outreach",
            "reviewer": "Ops",
        },
    )
    assert _state(client, business_id) == "OUTREACH_READY"
    _submit(client, page, r"/outreach-log$", {"operator": "Ops", "notes": "Sent from my own mailbox"})
    assert _state(client, business_id) == "CONTACTED"
    _submit(
        client,
        page,
        r"/crm-event$",
        {"event_type": "reply_received", "summary": "Asked for pricing", "operator": "Ops"},
    )
    assert _state(client, business_id) == "REPLIED"
    _submit(client, page, r"/follow-ups$", {"reason": "Send pricing", "due_at": "2026-10-05T10:00"})
    assert "Send pricing" in client.get("/ui/queues/follow-up").text


def test_LBOE_AUD_110_consent_step_requires_a_stated_basis(client: Any, seed: Any) -> None:
    """The consent form must not let an operator approve with the default 'unknown' basis."""
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    demo = seed.demo(business_id)
    seed.approve(demo["id"])
    page = f"/ui/businesses/{business_id}"
    _submit(client, page, r"/outreach-draft$", {"channels": ["email"]})
    _submit(client, page, r"/outreach-readiness$", {"reviewer": "Ops"})
    soup = _soup(client, page)
    basis = soup.find("select", attrs={"name": "consent_basis_type"})
    assert basis is not None and basis.get("required") is not None
    first = basis.find("option")
    assert first is not None and first.get("value") == "", "a real basis must be chosen, not defaulted"


# --- Safety legibility ----------------------------------------------------------------------


def test_LBOE_AUD_111_suppressed_business_page_is_unambiguous(client: Any, seed: Any) -> None:
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1, website="https://suppressed-audit.example")
    seed.score_and_brief(business_id)  # score predates the suppression, as in real use
    response = client.post(f"/v1/businesses/{business_id}/suppressions", json={"reason": "owner opted out"})
    assert response.status_code == 201
    soup = _soup(client, f"/ui/businesses/{business_id}")
    text = soup.get_text(" ", strip=True)
    assert "No identity, suppression, or policy holds are blocking this lead" not in text
    alert = soup.find(attrs={"role": "alert"})
    assert alert is not None and "suppress" in alert.get_text().lower(), "no prominent suppression alert"
    actions = {i.get("value") for i in soup.select("form[action$='/action'] input[name=action]")}
    assert not actions, f"suppressed lead still offers pipeline actions: {actions}"


def test_LBOE_AUD_121_identity_badge_is_not_hard_coded(client: Any, seed: Any) -> None:
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    text = _soup(client, f"/ui/businesses/{business_id}").get_text(" ", strip=True)
    assert "Verified identity" not in text, "unscored, unaudited lead is labelled 'Verified identity'"


def test_LBOE_AUD_121_review_prompt_does_not_call_unreviewed_demos_approved(client: Any, seed: Any) -> None:
    _no_website_demo(seed)  # at least one lead in REVIEW_PENDING
    text = _soup(client, "/ui").get_text(" ", strip=True)
    assert "Approved concepts are waiting for a human decision" not in text


# --- Prospect-facing preview ----------------------------------------------------------------


def _preview(client: Any, seed: Any) -> Any:
    _business_id, demo = _no_website_demo(seed)
    html = client.post(f"/ui/demos/{demo['id']}/preview-links", data={"label": "audit", "expires_days": "7"}).text
    token_path = re.search(r"/preview/[A-Za-z0-9_-]+", html)
    assert token_path, html[:300]
    return client.get(token_path.group(0)), token_path.group(0)


def test_LBOE_AUD_112_prospect_preview_is_styled(client: Any, seed: Any) -> None:
    response, path = _preview(client, seed)
    soup = BeautifulSoup(response.text, "html.parser")
    if soup.find("style"):
        return
    hrefs = [link["href"] for link in soup.find_all("link", rel="stylesheet")]
    base = path.rsplit("/", 1)[0] + "/"
    statuses = {href: client.get(href if href.startswith("/") else base + href).status_code for href in hrefs}
    assert statuses and all(code == 200 for code in statuses.values()), f"stylesheet not served: {statuses}"


def test_LBOE_AUD_112_prospect_preview_is_not_indexable_or_cached(client: Any, seed: Any) -> None:
    response, _path = _preview(client, seed)
    soup = BeautifulSoup(response.text, "html.parser")
    meta = soup.find("meta", attrs={"name": "robots"})
    robots = (response.headers.get("x-robots-tag", "") + " " + (meta.get("content", "") if meta else "")).lower()
    assert "noindex" in robots, "concept previews can be indexed as look-alike sites"
    assert "no-store" in response.headers.get("cache-control", ""), "tokenised preview may be cached by proxies"
    assert response.headers.get("referrer-policy") == "no-referrer", "token URL can leak via Referer"


def test_LBOE_AUD_112_prospect_preview_has_no_dead_placeholder_links(client: Any, seed: Any) -> None:
    response, _path = _preview(client, seed)
    soup = BeautifulSoup(response.text, "html.parser")
    ids = {tag.get("id") for tag in soup.find_all(id=True)}
    dead = [a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("#") and a["href"][1:] not in ids]
    assert not dead, f"in-page links point at missing anchors: {dead}"


# --- Demo QA false failures -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "address"),
    [
        ("Anne's Hair Studio", "12 Kloof Street, Gardens"),
        ("Crown & Co Barbers", "12 Kloof Street, Gardens"),
        ("Colour 360 Salon", "12 Kloof Street, Gardens"),
        ("Hair 2 Go", "12 Kloof Street, Gardens"),
        ("Fynbos Beauty", "Shop 4, Floor 1, 20 Main Road, Somerset West"),
        ("Fynbos Beauty", "Unit 3, 88 R44, Stellenbosch"),
    ],
)
def test_LBOE_AUD_113_demo_qa_accepts_ordinary_business_facts(name: str, address: str, tmp_path: Path) -> None:
    """Measured: 17 of 51 synthetic demos (33%) failed QA only because of '&', apostrophes or 'r'+digit text."""
    from types import SimpleNamespace

    from lboe_api.demo_generator import qa_demo, render_demo, write_artifacts

    demo_id = uuid.uuid4()
    business = SimpleNamespace(id=uuid.uuid4(), display_name=name, category="Hair salon", locality="Cape Town")
    brief = {"id": str(uuid.uuid4()), "facts": {"identity": [{"label": "address", "value": address}]}}
    rendered = render_demo(demo_id, business, brief, "starter_website")
    write_artifacts(tmp_path, demo_id, rendered)
    status, checks = qa_demo(tmp_path, demo_id, rendered)
    assert status == "passed", {code: ok for code, ok in checks.items() if not ok}


# --- Operator-facing content ----------------------------------------------------------------


def test_LBOE_AUD_118_queues_do_not_use_uuids_as_link_text(client: Any, seed: Any) -> None:
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    client.post(
        f"/v1/businesses/{business_id}/follow-ups",
        json={"reason": "Call back", "due_at": datetime(2026, 10, 2, 7, 0, tzinfo=UTC).isoformat()},
    )
    offenders = [
        (path, a.get_text(strip=True))
        for path in ("/ui/queues/follow-up", "/ui/queues/proposal-ready", f"/ui/businesses/{business_id}")
        for a in _soup(client, path).find_all("a")
        if UUID_RE.search(a.get_text())
    ]
    assert not offenders, f"raw identifiers used as link text: {offenders[:5]}"


def test_LBOE_AUD_119_times_are_shown_in_operator_timezone(client: Any, seed: Any) -> None:
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    reason = f"Call back {uuid.uuid4().hex[:6]}"
    client.post(
        f"/v1/businesses/{business_id}/follow-ups",
        json={"reason": reason, "due_at": "2026-10-02T09:00:00+02:00"},
    )
    row = next(
        tr.get_text(" ", strip=True) for tr in _soup(client, "/ui/queues/follow-up").find_all("tr") if reason in tr.text
    )
    # 09:00 SAST must read as 09:00 - not as raw ISO with an offset (Postgres returns "07:00:00+00:00").
    assert "09:00" in row, row
    assert not re.search(r"[+-]\d{2}:\d{2}\b|\d{2}:\d{2}:\d{2}", row), f"raw timestamp shown to operator: {row}"


def test_LBOE_AUD_120_ui_errors_render_as_pages_not_json(client: Any, seed: Any) -> None:
    business_id, demo = _no_website_demo(seed)
    client.post(f"/v1/businesses/{business_id}/suppressions", json={"reason": "opted out"})  # sharing now 409s
    for method, path, data in (
        ("post", f"/ui/demos/{demo['id']}/preview-links", {"label": "x", "expires_days": "7"}),
        ("get", f"/ui/businesses/{uuid.uuid4()}", None),
        ("get", "/ui/queues/does-not-exist", None),
    ):
        response = getattr(client, method)(path, data=data) if data else getattr(client, method)(path)
        assert response.status_code >= 400
        assert response.headers["content-type"].startswith("text/html"), f"{path}: raw {response.text[:80]}"
        assert "<main" in response.text


def test_LBOE_AUD_120_comment_on_unknown_business_is_404_not_500(client: Any) -> None:
    try:
        response = client.post(f"/ui/businesses/{uuid.uuid4()}/comment", data={"body": "x"}, follow_redirects=False)
        status = response.status_code
    except Exception as exc:  # noqa: BLE001 - TestClient re-raises server errors
        status = type(exc).__name__
    assert status == 404, status


# --- Accessibility (static, dialect independent) --------------------------------------------

A11Y_PAGES = ["/ui", "/ui/campaigns", "/ui/operators", "/ui/pilots/new", "/ui/login"]


def _contrast(foreground: str, background: str) -> float:
    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_LBOE_AUD_114_design_tokens_meet_wcag_aa_contrast() -> None:
    css = (TARGET / "apps/api/src/lboe_api/static/ui.css").read_text(encoding="utf-8")
    tokens = {
        name: value if len(value) == 7 else "#" + "".join(ch * 2 for ch in value[1:])
        for name, value in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b", css)
    }
    eyebrow = re.search(r"\.eyebrow\{[^}]*color:\s*(var\(--[\w-]+\)|#[0-9a-fA-F]{6})", css)
    assert eyebrow
    eyebrow_colour = eyebrow.group(1)
    if eyebrow_colour.startswith("var"):
        eyebrow_colour = tokens[eyebrow_colour[6:-1]]
    pairs = {
        "muted text on page": (tokens["muted"], tokens["paper"]),
        "link in muted text on page": (tokens["blue"], tokens["paper"]),
        "eyebrow on page": (eyebrow_colour, tokens["paper"]),
        "eyebrow on card": (eyebrow_colour, tokens["card"]),
    }
    failures = {name: round(_contrast(*pair), 2) for name, pair in pairs.items() if _contrast(*pair) < 4.5}
    assert not failures, f"WCAG 1.4.3 AA contrast below 4.5:1: {failures}"


@pytest.mark.parametrize("path", A11Y_PAGES)
def test_LBOE_AUD_115_form_controls_have_labels(client: Any, seed: Any, path: str) -> None:
    seed.campaign()
    soup = _soup(client, path)
    unlabeled = []
    for control in soup.select("input:not([type=hidden]), select, textarea"):
        control_id = control.get("id")
        labelled = (
            control.find_parent("label")
            or (control_id and soup.find("label", attrs={"for": control_id}))
            or control.get("aria-label")
            or control.get("aria-labelledby")
        )
        if not labelled:
            unlabeled.append(control.get("name"))
    assert not unlabeled, f"controls without an accessible label (placeholder is not a label): {unlabeled}"


def test_LBOE_AUD_115_business_page_controls_have_labels(client: Any, seed: Any) -> None:
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    test_LBOE_AUD_115_form_controls_have_labels(client, seed, f"/ui/businesses/{business_id}")


@pytest.mark.parametrize("path", A11Y_PAGES)
def test_LBOE_AUD_116_page_structure(client: Any, seed: Any, path: str) -> None:
    seed.campaign()
    soup = _soup(client, path)
    assert len(soup.find_all("h1")) == 1, f"{path}: {len(soup.find_all('h1'))} <h1> elements"
    skip = soup.find("a", href="#main")
    main = soup.find("main")
    assert skip is not None and main is not None and main.get("id") == "main", "no skip link to #main"
    body_children = [c for c in soup.body.find_all(recursive=False) if c.name]
    outside = [
        c.name + "." + ".".join(c.get("class", []))
        for c in body_children
        if c.name not in {"header", "main", "footer", "nav", "a", "aside"}
    ]
    assert not outside, f"content outside landmarks: {outside}"
    for th in soup.find_all("th"):
        assert th.get("scope") in {"col", "row"}, f"{path}: <th> without scope"


def test_LBOE_AUD_117_mobile_navigation_targets_are_at_least_24px() -> None:
    css = (TARGET / "apps/api/src/lboe_api/static/ui.css").read_text(encoding="utf-8")
    rule = re.search(r"(?:^|\})\s*(?:header )?nav a\s*\{([^}]*)\}", css)
    assert rule, "no 'nav a' rule"
    min_height = re.search(r"min-height:\s*(\d+)px", rule.group(1))
    padding = re.search(r"padding:\s*(\d+)px", rule.group(1))
    assert (min_height and int(min_height.group(1)) >= 24) or (padding and int(padding.group(1)) >= 6), (
        "nav links render ~17px tall: below the WCAG 2.2 SC 2.5.8 24x24 minimum"
    )


def test_LBOE_AUD_122_dashboard_counts_failed_and_blocked_jobs(client: Any, seed: Any) -> None:
    """The dashboard tile reads report keys that do not exist, so it always shows 0."""
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    seed.score_and_brief(business_id)
    refused = client.post(f"/v1/businesses/{business_id}/proposal", json={"idempotency_key": uuid.uuid4().hex})
    assert refused.json()["status"] == "not_proposal_eligible"  # recorded as a not_eligible job
    soup = _soup(client, "/ui")
    line = next(div for div in soup.select(".stat-line") if "Failed / blocked jobs" in div.get_text())
    assert int(line.find("strong").get_text()) >= 1, line.get_text(" ", strip=True)


def test_LBOE_AUD_123_recommended_step_follows_the_lifecycle_stage(client: Any, seed: Any) -> None:
    """A lead awaiting a human decision must not be told to 'run optional enrichment'."""
    campaign = seed.campaign()
    [business_id] = seed.businesses(campaign, 1)
    demo = seed.demo(business_id)
    assert demo["status"] == "qa_passed"
    hero = _soup(client, f"/ui/businesses/{business_id}").select_one("section.next-action")
    assert hero is not None
    text = hero.get_text(" ", strip=True).lower()
    assert "review" in text and "concept" in text, text
    assert hero.find("a", href="#workflow") is not None, "hero does not lead to the pending human decision"
    assert not hero.select("form input[name=action]"), "hero offers an automated action instead of the decision"
