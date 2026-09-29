"""Audit regression suite bootstrap.

Every test in this directory is named after the finding it guards and is
written to FAIL on the audited baseline (cc56bda) and PASS once the fix lands.

Select the checkout under test with ``LBOE_AUDIT_TARGET`` (defaults to this
repository).  Run from the repository root:

    .venv-audit/bin/pytest -c audit/tests/pytest.ini                         # baseline
    LBOE_AUDIT_TARGET=/path/to/patched pytest -c audit/tests/pytest.ini      # after fixes
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

AUDIT_DIR = Path(__file__).resolve().parents[1]
TARGET = Path(os.environ.get("LBOE_AUDIT_TARGET", AUDIT_DIR.parent)).resolve()
for relative in (
    "integrations/website_auditor/src",
    "integrations/maps_scraper/src",
    "packages/scoring/src",
    "packages/domain/src",
    "apps/api/src",
):
    sys.path.insert(0, str(TARGET / relative))
sys.path.insert(0, str(AUDIT_DIR / "lab"))

os.environ["LBOE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["LBOE_REDIS_URL"] = "redis://localhost:63999/0"
os.environ["LBOE_AUTO_CREATE_SCHEMA"] = "true"
os.environ.setdefault("LBOE_DEMO_ARTIFACT_ROOT", str(Path(os.environ.get("TMPDIR", "/tmp")) / "lboe-audit-artifacts"))
os.environ.setdefault("LBOE_EXPORT_ROOT", str(Path(os.environ.get("TMPDIR", "/tmp")) / "lboe-audit-exports"))
# The app mounts its static directory relative to the working directory (lead L11).
os.chdir(TARGET)

CHECKLIST = [
    "concept_banner_visible",
    "business_name_correct",
    "not_claiming_official_site",
    "no_fake_prices",
    "no_fake_testimonials",
    "no_unsupported_awards",
    "contact_links_safe",
    "source_claims_supported",
    "no_outreach_content",
    "appropriate_demo_type",
    "preview_opens_locally",
    "no_sensitive_or_prohibited_content",
]


@pytest.fixture(scope="session")
def app_module() -> Any:
    import lboe_api.main as module
    from offline_audit import OfflineAuditAdapter

    module.set_audit_adapter(OfflineAuditAdapter())
    assert Path(module.__file__).resolve().is_relative_to(TARGET), "imported app is not the audit target"
    return module


@pytest.fixture(scope="session")
def client(app_module: Any) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client


def _ok(response: Any) -> dict[str, Any]:
    assert response.status_code < 400, response.text[:400]
    return response.json()  # type: ignore[no-any-return]


class Seeder:
    """Builds synthetic records through the application's own API."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def campaign(self) -> str:
        body = {"name": f"audit-{uuid.uuid4().hex[:8]}", "vertical": "hair-salon", "geography": "Cape Town"}
        return str(_ok(self.client.post("/v1/campaigns", json=body))["id"])

    def businesses(self, campaign_id: str, count: int, **overrides: Any) -> list[str]:
        records = []
        for index in range(count):
            record = {
                "display_name": f"Synthetic Studio {uuid.uuid4().hex[:10]}",
                "category": "Hair salon",
                "locality": "Observatory",
                "address_text": "12 Lower Main Road, Observatory, Cape Town",
                "phone": f"+27 21 555 {index:04d}",
                "rating": "4.1",
                "review_count": "12",
            }
            record.update(overrides)
            records.append(record)
        result = _ok(
            self.client.post(f"/v1/campaigns/{campaign_id}/import", json={"format": "json", "records": records})
        )
        return [item["business_id"] for item in result["successes"]]

    def score_and_brief(self, business_id: str) -> None:
        _ok(self.client.post(f"/v1/businesses/{business_id}/audit", json={"idempotency_key": "audit"}))
        _ok(self.client.post(f"/v1/businesses/{business_id}/score", json={"idempotency_key": "audit"}))
        _ok(self.client.post(f"/v1/businesses/{business_id}/brief", json={"idempotency_key": "audit"}))

    def demo(self, business_id: str) -> dict[str, Any]:
        self.score_and_brief(business_id)
        return _ok(self.client.post(f"/v1/businesses/{business_id}/demo", json={"idempotency_key": "audit"}))

    def approve(self, demo_id: str) -> dict[str, Any]:
        checklist = [{"code": code, "label": code, "passed": True} for code in CHECKLIST]
        body = {"decision": "approve", "reviewer": "audit", "checklist": checklist}
        return _ok(self.client.post(f"/v1/demos/{demo_id}/review", json=body))


@pytest.fixture()
def seed(client: Any) -> Seeder:
    return Seeder(client)


class StatementCounter:
    def __init__(self, engine: Any) -> None:
        from sqlalchemy import event
        from sqlalchemy.orm import Session

        self.statements = 0
        self.rows = 0  # ORM instances materialised (dialect independent)
        event.listen(engine, "before_cursor_execute", self._before)
        event.listen(Session, "loaded_as_persistent", self._loaded)
        self.engine = engine

    def _before(self, *_args: Any, **_kwargs: Any) -> None:
        self.statements += 1

    def _loaded(self, *_args: Any, **_kwargs: Any) -> None:
        self.rows += 1

    def reset(self) -> None:
        self.statements = 0
        self.rows = 0

    def close(self) -> None:
        from sqlalchemy import event
        from sqlalchemy.orm import Session

        event.remove(self.engine, "before_cursor_execute", self._before)
        event.remove(Session, "loaded_as_persistent", self._loaded)


@pytest.fixture()
def sql(app_module: Any) -> Iterator[StatementCounter]:
    counter = StatementCounter(app_module.engine)
    yield counter
    counter.close()
