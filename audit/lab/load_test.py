"""Concurrent load test against a running LBOE server (WS-P / WS-J).

Fires ``--requests`` GETs at ``--path`` with ``--concurrency`` in-flight requests
and samples PostgreSQL ``pg_stat_activity`` for the target database while the
load runs.  Reports status histogram, latency percentiles, throughput, and
peak/final server-side connections - which exposes session leaks and
connection-pool exhaustion (SQLAlchemy default QueuePool: 5 + 10 overflow,
30 s checkout timeout).

    python audit/lab/load_test.py --base http://127.0.0.1:8001 --path /ui/businesses/<id> \
        --requests 300 --concurrency 20 --db lboe_s100 --out audit/evidence/perf/load_ui_business.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter
from pathlib import Path

import httpx
import psycopg


async def sample_connections(dsn: str, db: str, stop: asyncio.Event, samples: list[int]) -> None:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        while not stop.is_set():
            cur = await conn.execute(
                "select count(*) from pg_stat_activity where datname = %s and pid <> pg_backend_pid()", (db,)
            )
            row = await cur.fetchone()
            samples.append(int(row[0]) if row else 0)
            await asyncio.sleep(0.2)


async def run(args: argparse.Namespace) -> dict[str, object]:
    dsn = f"postgresql://lboe:{args.pg_password}@localhost:5432/{args.db}"
    stop = asyncio.Event()
    samples: list[int] = []
    sampler = asyncio.create_task(sample_connections(dsn, args.db, stop, samples))
    await asyncio.sleep(0.5)
    baseline = samples[-1] if samples else None
    latencies: list[float] = []
    statuses: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(base_url=args.base, timeout=args.timeout) as client:

        async def one() -> None:
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(args.path)
                    statuses[str(response.status_code)] += 1
                except httpx.HTTPError as exc:
                    statuses[type(exc).__name__] += 1
                latencies.append(time.perf_counter() - started)

        wall = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(args.requests)))
        wall = time.perf_counter() - wall
    await asyncio.sleep(2)
    stop.set()
    await sampler
    ordered = sorted(latencies)
    return {
        "path": args.path,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "statuses": dict(statuses),
        "throughput_rps": round(args.requests / wall, 1),
        "p50_ms": round(statistics.median(ordered) * 1000, 1),
        "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1] * 1000, 1),
        "max_ms": round(ordered[-1] * 1000, 1),
        "pg_connections_baseline": baseline,
        "pg_connections_peak": max(samples) if samples else None,
        "pg_connections_after": samples[-1] if samples else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--db", required=True)
    parser.add_argument("--pg-password", default="lboe_dev_only")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    print(json.dumps(result, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(args.out.read_text()) if args.out.exists() else []
        existing.append(result)
        args.out.write_text(json.dumps(existing, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
