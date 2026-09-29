# ruff: noqa: E501  (embedded JavaScript probes)
"""Browser-level UX and accessibility audit of the LBOE operator UI (WS-O).

For every page in ``PAGES`` and every viewport it:
  * takes a full-page JPEG screenshot  -> audit/evidence/ui/<slug>-<viewport>.jpg
  * runs axe-core (WCAG 2.0/2.1/2.2 A+AA rule tags)
  * measures horizontal overflow and the elements causing it
  * counts interactive targets smaller than 24x24 CSS px (WCAG 2.2 SC 2.5.8)
  * records heading outline, landmark presence, unlabeled controls, raw-UUID link text
Keyboard pass (desktop only): tab order length, skip link, visible focus indicator.

    python audit/lab/ui_audit.py --base http://127.0.0.1:8001 --pages audit/evidence/ui/pages.json \
        --axe /tmp/claude-0/node/node_modules/axe-core/axe.min.js --out audit/evidence/ui
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

VIEWPORTS = {
    "desktop-1440": {"width": 1440, "height": 900},
    "laptop-1024": {"width": 1024, "height": 768},
    "tablet-768": {"width": 768, "height": 1024},
    "mobile-390": {"width": 390, "height": 844},
}
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

PAGE_PROBE = """
() => {
  const vw = document.documentElement.clientWidth;
  const overflowing = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > vw + 1 && getComputedStyle(el).position !== 'fixed') {
      overflowing.push(el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''));
    }
  }
  const interactive = [...document.querySelectorAll('a[href], button, input, select, textarea, summary')]
    .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const small = interactive.filter(el => {
    const r = el.getBoundingClientRect();
    return (r.width < 24 || r.height < 24) && !(el.tagName === 'A' && getComputedStyle(el).display === 'inline');
  });
  const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => h.tagName + ':' + h.textContent.trim().slice(0, 60));
  const controls = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')];
  const unlabeled = controls.filter(c => {
    if (c.labels && c.labels.length) return false;
    return !(c.getAttribute('aria-label') || c.getAttribute('aria-labelledby') || c.getAttribute('title'));
  }).map(c => (c.getAttribute('name') || c.tagName) + (c.placeholder ? ' [placeholder only]' : ''));
  const uuidLinks = [...document.querySelectorAll('a')].filter(a => /UUID_RE/.test(a.textContent.trim())).length;
  const text = document.body.innerText;
  return {
    scrollWidth: document.documentElement.scrollWidth, clientWidth: vw,
    overflowCount: overflowing.length, overflowSample: [...new Set(overflowing)].slice(0, 8),
    interactiveCount: interactive.length, smallTargets: small.length,
    smallTargetSample: small.slice(0, 5).map(e => e.tagName.toLowerCase() + ':' + (e.textContent || e.name || '').trim().slice(0, 30)),
    h1Count: document.querySelectorAll('h1').length, headings: headings.slice(0, 30),
    landmarks: { main: !!document.querySelector('main'), nav: !!document.querySelector('nav'),
                 header: !!document.querySelector('header'), skipLink: !!document.querySelector('a[href="#main"], a.skip-link') },
    unlabeledControls: unlabeled, uuidLinkText: uuidLinks,
    tables: document.querySelectorAll('table').length,
    tableHeadersWithScope: document.querySelectorAll('th[scope]').length,
    tableHeaders: document.querySelectorAll('th').length,
    captions: document.querySelectorAll('caption').length,
    jargon: (text.match(/\\b(DISCOVERED|APPROVED_FOR_OUTREACH|OUTREACH_READY|CONSENT_PENDING|REVIEW_PENDING|qa_passed|qa_failed|not_eligible|score_only|do_not_contact|audit_required|manual_review|generate_demo|conversion_upgrade_offer|technical_cleanup_offer)\\b/g) || []).length,
    rawUuidsInText: (text.match(/UUID_RE/g) || []).length,
    words: text.split(/\\s+/).length,
  };
}
""".replace("UUID_RE", UUID_RE)

FOCUS_PROBE = """
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const s = getComputedStyle(el);
  const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0;
  const shadow = s.boxShadow && s.boxShadow !== 'none';
  return { tag: el.tagName.toLowerCase(), text: (el.textContent || el.name || '').trim().slice(0, 40),
           visibleIndicator: outline || shadow, outline: s.outlineStyle + ' ' + s.outlineWidth };
}
"""


async def audit_page(page: Page, url: str, axe_source: str, run_axe: bool) -> dict[str, Any]:
    response = await page.goto(url, wait_until="load", timeout=120_000)
    result: dict[str, Any] = {"status": response.status if response else None}
    result["probe"] = await page.evaluate(PAGE_PROBE)
    if run_axe:
        await page.add_script_tag(content=axe_source)
        axe = await page.evaluate(
            "async (tags) => { const r = await axe.run(document, {runOnly: {type: 'tag', values: tags}}); "
            "return r.violations.map(v => ({id: v.id, impact: v.impact, tags: v.tags, help: v.help, "
            "nodes: v.nodes.length, sample: v.nodes.slice(0, 3).map(n => n.target.join(' '))})); }",
            AXE_TAGS,
        )
        result["axe"] = axe
    return result


async def keyboard_pass(page: Page, url: str, max_tabs: int = 80) -> dict[str, Any]:
    await page.goto(url, wait_until="load", timeout=120_000)
    stops: list[dict[str, Any]] = []
    for _ in range(max_tabs):
        await page.keyboard.press("Tab")
        info = await page.evaluate(FOCUS_PROBE)
        if info is None:
            break
        stops.append(info)
    first_main = next((i for i, s in enumerate(stops) if s["tag"] in {"input", "button", "select", "textarea"}), None)
    return {
        "tab_stops_sampled": len(stops),
        "stops_without_visible_indicator": sum(1 for s in stops if not s["visibleIndicator"]),
        "first_stop": stops[0] if stops else None,
        "tabs_before_first_form_control": first_main,
        "sample": stops[:12],
    }


async def main_async(args: argparse.Namespace) -> None:
    pages: dict[str, str] = json.loads(Path(args.pages).read_text())
    axe_source = Path(args.axe).read_text()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"viewports": VIEWPORTS, "pages": {}}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for vp_name, size in VIEWPORTS.items():
            context = await browser.new_context(viewport=size, reduced_motion="reduce")
            page = await context.new_page()
            for slug, path in pages.items():
                url = args.base + path
                run_axe = vp_name in {"desktop-1440", "mobile-390"}
                try:
                    data = await audit_page(page, url, axe_source, run_axe)
                    shot = out / f"{slug}-{vp_name}.jpg"
                    await page.screenshot(path=str(shot), full_page=True, type="jpeg", quality=55)
                    data["screenshot"] = str(shot)
                except Exception as exc:  # noqa: BLE001 - record and continue the sweep
                    data = {"error": f"{type(exc).__name__}: {exc}"[:300]}
                report["pages"].setdefault(slug, {"path": path})[vp_name] = data
                print(vp_name, slug, data.get("status"), len(data.get("axe", [])) if "axe" in data else "")
            await context.close()
        context = await browser.new_context(viewport=VIEWPORTS["desktop-1440"])
        page = await context.new_page()
        report["keyboard"] = {}
        for slug in args.keyboard_pages.split(","):
            report["keyboard"][slug] = await keyboard_pass(page, args.base + pages[slug])
        report["aria_snapshots"] = {}
        for slug in args.keyboard_pages.split(","):
            await page.goto(args.base + pages[slug], wait_until="load")
            report["aria_snapshots"][slug] = await page.locator("body").aria_snapshot()
        await browser.close()
    (out / "ui_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--pages", required=True, help="JSON object slug -> path")
    parser.add_argument("--axe", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--keyboard-pages", default="dashboard,business-worked,campaign,login")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
