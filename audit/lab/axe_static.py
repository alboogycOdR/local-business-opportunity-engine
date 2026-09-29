"""Run axe-core on a saved HTML document (for CSP-protected pages such as concept previews).

python audit/lab/axe_static.py <file.html> <axe.min.js>
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def main(html_path: str, axe_path: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        results = {}
        for name, size in (("desktop-1440", (1440, 900)), ("mobile-390", (390, 844))):
            page = await browser.new_page(viewport={"width": size[0], "height": size[1]})
            await page.set_content(Path(html_path).read_text(encoding="utf-8"))
            await page.add_script_tag(content=Path(axe_path).read_text(encoding="utf-8"))
            results[name] = await page.evaluate(
                "async () => (await axe.run(document, {runOnly: {type: 'tag', values: "
                "['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations"
                ".map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length}))"
            )
            await page.screenshot(
                path=html_path.replace(".html", f"-{name}.jpg"), full_page=True, type="jpeg", quality=60
            )
        await browser.close()
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
