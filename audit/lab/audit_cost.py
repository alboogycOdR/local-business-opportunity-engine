"""Measure the cost of one Playwright homepage audit (browser stage only) against a benign local page.

The resolver stage is skipped (it rejects loopback by design); this isolates Chromium wall time,
peak RSS of the browser process tree and screenshot bytes - the inputs to the capacity model.
    python audit/lab/audit_cost.py http://127.0.0.1:8765/ 5
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/domain/src"), str(ROOT / "integrations/website_auditor/src")]
import psutil  # noqa: E402
from lboe_domain import AuditRequest, WebsiteResolutionResult  # noqa: E402
from lboe_website_auditor import PlaywrightAuditAdapter  # noqa: E402


async def sample_rss(stop: asyncio.Event, peaks: list[int]) -> None:
    me = psutil.Process()
    while not stop.is_set():
        total = me.memory_info().rss
        for child in me.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                pass
        peaks.append(total)
        await asyncio.sleep(0.05)


async def main(url: str, runs: int) -> None:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        adapter = PlaywrightAuditAdapter(tmp, 1)
        for _ in range(runs):
            request = AuditRequest(business_id=uuid.uuid4(), website_url=url, timeout_seconds=30)
            resolution = WebsiteResolutionResult(requested_url=url, final_url=url, status="healthy", http_status=200)
            stop, peaks = asyncio.Event(), []
            sampler = asyncio.create_task(sample_rss(stop, peaks))
            started = time.perf_counter()
            result = await adapter._browser_audit(request, resolution, [])
            elapsed = time.perf_counter() - started
            stop.set()
            await sampler
            results.append(
                {
                    "seconds": round(elapsed, 2),
                    "peak_rss_mb": round(max(peaks) / 2**20, 1),
                    "screenshot_bytes": sum(a.byte_size or 0 for a in result.artifacts),
                    "findings": len(result.findings),
                }
            )
    summary = {
        "runs": results,
        "median_seconds": statistics.median(r["seconds"] for r in results),
        "median_screenshot_kb": round(statistics.median(r["screenshot_bytes"] for r in results) / 1024, 1),
        "max_peak_rss_mb": max(r["peak_rss_mb"] for r in results),
    }
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5))
