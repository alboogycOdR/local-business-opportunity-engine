"""Build the before/after route-latency table in REPORT.md from route_profiler JSON files.

    python audit/tools/perf_table.py            # prints Markdown
"""

from __future__ import annotations

import json
from pathlib import Path

PERF = Path(__file__).resolve().parents[1] / "evidence" / "perf"
COLUMNS = [
    ("100 base", "routes_s100.json"),
    ("1k base", "routes_s1000.json"),
    ("10k base", "routes_s10000_baseline.json"),
    ("1k patched", "routes_s1000_patched.json"),
    ("10k patched", "routes_s10000_patched.json"),
]
ROUTES = [
    "/ui",
    "/ui/opportunities",
    "/ui/campaigns/{campaign_id}",
    "/ui/queues/no-demo-reason",
    "/ui/queues/weak-evidence",
    "/ui/queues",
    "/ui/campaigns",
    "/ui/businesses/{business_id}",
    "/ui/reports/pilot",
    "/ui/campaigns/{campaign_id}/reports/pilot",
    "/v1/reports/pilot",
    "/v1/businesses",
]


def load(name: str) -> dict[str, dict[str, object]]:
    path = PERF / name
    if not path.exists():
        return {}
    return {row["path"]: row for row in json.loads(path.read_text())["routes"] if "p50_ms" in row}


def cell(row: dict[str, object] | None) -> str:
    if not row:
        return "—"
    ms = float(row["p50_ms"])  # type: ignore[arg-type]
    shown = f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms:.0f} ms"
    return f"{shown} / {row['sql_statements']}"


def main() -> None:
    data = [(title, load(name)) for title, name in COLUMNS]
    print("| Route | " + " | ".join(title for title, _ in data) + " |")
    print("|---|" + "---|" * len(data))
    for route in ROUTES:
        print(f"| `{route}` | " + " | ".join(cell(rows.get(route)) for _title, rows in data) + " |")


if __name__ == "__main__":
    main()
