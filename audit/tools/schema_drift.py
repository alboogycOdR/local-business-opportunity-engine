"""Compare SQLAlchemy ORM metadata (used by tests via create_all) with the schema
produced by the hand-written SQL migrations on a real PostgreSQL database.

Usage: python audit/tools/schema_drift.py postgresql+psycopg://user:pw@host/db
Writes a JSON + Markdown drift report to stdout.
"""

from __future__ import annotations

import json
import sys

from sqlalchemy import create_engine, inspect

sys.path[:0] = [
    "apps/api/src",
    "packages/domain/src",
    "packages/scoring/src",
    "integrations/maps_scraper/src",
    "integrations/website_auditor/src",
]
from lboe_api.db import Base  # noqa: E402


def main(url: str) -> int:
    engine = create_engine(url)
    insp = inspect(engine)
    db_tables = set(insp.get_table_names()) - {"schema_migrations"}
    orm_tables = set(Base.metadata.tables)
    report: dict[str, object] = {
        "tables_only_in_orm": sorted(orm_tables - db_tables),
        "tables_only_in_migrations": sorted(db_tables - orm_tables),
        "column_drift": {},
        "nullability_drift": {},
        "unique_drift": {},
        "fk_drift": {},
        "index_counts": {},
    }
    for name in sorted(orm_tables & db_tables):
        orm_t = Base.metadata.tables[name]
        db_cols = {c["name"]: c for c in insp.get_columns(name)}
        orm_cols = {c.name: c for c in orm_t.columns}
        only_orm = sorted(set(orm_cols) - set(db_cols))
        only_db = sorted(set(db_cols) - set(orm_cols))
        if only_orm or only_db:
            report["column_drift"][name] = {"only_in_orm": only_orm, "only_in_db": only_db}  # type: ignore[index]
        nulls = []
        for col in set(orm_cols) & set(db_cols):
            if bool(orm_cols[col].nullable) != bool(db_cols[col]["nullable"]):
                nulls.append(
                    {"column": col, "orm_nullable": orm_cols[col].nullable, "db_nullable": db_cols[col]["nullable"]}
                )
        if nulls:
            report["nullability_drift"][name] = nulls  # type: ignore[index]
        db_uniques = {tuple(sorted(u["column_names"])) for u in insp.get_unique_constraints(name)}
        db_uniques |= {tuple(sorted(i["column_names"])) for i in insp.get_indexes(name) if i.get("unique")}
        pk = insp.get_pk_constraint(name).get("constrained_columns") or []
        orm_uniques = set()
        for c in orm_t.constraints:
            if c.__class__.__name__ == "UniqueConstraint":
                orm_uniques.add(tuple(sorted(col.name for col in c.columns)))
        for col in orm_t.columns:
            if col.unique:
                orm_uniques.add((col.name,))
        for idx in orm_t.indexes:
            if idx.unique:
                orm_uniques.add(tuple(sorted(c.name for c in idx.columns)))
        if orm_uniques != db_uniques:
            report["unique_drift"][name] = {  # type: ignore[index]
                "only_in_orm": sorted(map(list, orm_uniques - db_uniques)),
                "only_in_db": sorted(map(list, db_uniques - orm_uniques - {tuple(sorted(pk))})),
            }
        db_fks = {
            (tuple(f["constrained_columns"]), f["referred_table"], (f.get("options") or {}).get("ondelete"))
            for f in insp.get_foreign_keys(name)
        }
        orm_fks = {((fk.parent.name,), fk.column.table.name, fk.ondelete) for fk in orm_t.foreign_keys}
        if {(a, b) for a, b, _ in db_fks} != {(a, b) for a, b, _ in orm_fks}:
            report["fk_drift"][name] = {  # type: ignore[index]
                "only_in_orm": sorted(map(str, {(a, b) for a, b, _ in orm_fks} - {(a, b) for a, b, _ in db_fks})),
                "only_in_db": sorted(map(str, {(a, b) for a, b, _ in db_fks} - {(a, b) for a, b, _ in orm_fks})),
            }
        report["index_counts"][name] = {"db": len(insp.get_indexes(name)), "orm": len(orm_t.indexes)}  # type: ignore[index]
    print(json.dumps(report, indent=2, default=str))
    drift = any(
        report[k]
        for k in (
            "tables_only_in_orm",
            "tables_only_in_migrations",
            "column_drift",
            "nullability_drift",
            "unique_drift",
            "fk_drift",
        )
    )
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
