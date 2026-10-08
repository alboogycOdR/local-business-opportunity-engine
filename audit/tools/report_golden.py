"""Dump pilot reports produced by a given checkout, for before/after equivalence checks.

python audit/tools/report_golden.py <checkout-root> <database-url> <out.json>
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date

root, url, out = sys.argv[1:4]
sys.path[:0] = [
    f"{root}/apps/api/src",
    f"{root}/packages/domain/src",
    f"{root}/packages/scoring/src",
    f"{root}/integrations/maps_scraper/src",
    f"{root}/integrations/website_auditor/src",
]
from lboe_api.db import Business, make_session_factory  # noqa: E402
from lboe_api.reporting_service import build_pilot_report  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

Session = make_session_factory(url)
results: dict[str, object] = {}
timings: dict[str, float] = {}
with Session() as session:
    campaign = session.scalar(
        select(Business.campaign_id).group_by(Business.campaign_id).order_by(func.count().desc()).limit(1)
    )
    cases = {
        "global": {},
        "global_details": {"include_details": True},
        "vertical": {"vertical": "hair-salon"},
        "campaign": {"campaign_id": campaign, "include_details": True},
        "campaign_window": {"campaign_id": campaign, "start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31)},
        "empty_window": {"start_date": date(2020, 1, 1), "end_date": date(2020, 1, 2)},
    }
    for name, kwargs in cases.items():
        started = time.perf_counter()
        report = build_pilot_report(session, **kwargs)
        timings[name] = round(time.perf_counter() - started, 3)
        report.pop("generated_at")
        results[name] = report
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"reports": results, "timings_s": timings}, handle, indent=1, sort_keys=True, default=str)
print(json.dumps(timings))
