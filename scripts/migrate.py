"""Apply ordered PostgreSQL migrations exactly once.

Usage:
    python scripts/migrate.py --database-url "$LBOE_DATABASE_URL"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "infrastructure" / "database" / "migrations"


def apply_migrations(database_url: str) -> list[str]:
    if database_url.startswith("postgresql+psycopg://"):
        database_url = "postgresql://" + database_url.removeprefix("postgresql+psycopg://")
    files = sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not files:
        raise RuntimeError(f"No migrations found in {MIGRATIONS}")
    applied: list[str] = []
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        existing = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for path in files:
            if path.name in existing:
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("LBOE_DATABASE_URL") or os.getenv("DATABASE_URL") or "",
        help="PostgreSQL connection URL; defaults to LBOE_DATABASE_URL or DATABASE_URL",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or LBOE_DATABASE_URL/DATABASE_URL is required")
    applied = apply_migrations(args.database_url)
    print(f"Applied {len(applied)} migration(s).")
    for name in applied:
        print(f"- {name}")


if __name__ == "__main__":
    main()
