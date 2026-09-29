"""Dump Opportunity Cards built by a given checkout for before/after equivalence checks.

    python audit/tools/cards_golden.py <checkout-root> <database-url> <out.json>
"""

from __future__ import annotations

import json
import sys
import time

root, url, out = sys.argv[1:4]
sys.path[:0] = [
    f"{root}/apps/api/src",
    f"{root}/packages/domain/src",
    f"{root}/packages/scoring/src",
    f"{root}/integrations/maps_scraper/src",
    f"{root}/integrations/website_auditor/src",
]
import os  # noqa: E402

os.environ["LBOE_DATABASE_URL"] = url
os.chdir(root)
import lboe_api.main  # noqa: E402,F401  (ui.routes imports main; load it first)
from lboe_api.db import make_session_factory  # noqa: E402
from lboe_api.ui.routes import build_opportunity_cards  # noqa: E402

Session = make_session_factory(url)
with Session() as session:
    started = time.perf_counter()
    cards = build_opportunity_cards(session, limit=100000)
    elapsed = time.perf_counter() - started
with open(out, "w", encoding="utf-8") as handle:
    json.dump(cards, handle, indent=1, default=str)
print(json.dumps({"cards": len(cards), "seconds": round(elapsed, 2)}))
