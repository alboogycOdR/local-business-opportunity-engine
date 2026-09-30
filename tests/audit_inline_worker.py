"""Test-only bridge for the audit pack's pre-queue synchronous fixtures.

The production API remains asynchronous. This pytest plugin runs only the
network-free audit service inline after the API has committed its durable job,
so the older audit acceptance suite can continue exercising downstream UI
states without a Redis service or a production behavior change.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, cast
from uuid import UUID

import pytest


@pytest.fixture(autouse=True)
def audit_inline_worker(app_module: Any) -> Iterator[None]:
    from lboe_api.audit_service import persist_audit
    from lboe_api.db import Business
    from lboe_domain import AuditRequest

    original_publish_job = cast(Callable[[Any, Any], dict[str, Any]], app_module.publish_job)

    def publish_job(job: Any, session: Any) -> dict[str, Any]:
        if job.job_type != "AUDIT_WEBSITE" or job.status != "queued":
            return original_publish_job(job, session)

        business = session.get(Business, UUID(str(job.payload["business_id"])))
        if business is None:
            return original_publish_job(job, session)
        request = AuditRequest.model_validate(job.payload)
        audit = app_module.audit_adapter.audit(request)
        try:
            result = audit.send(None)
        except StopIteration as completed:
            result = completed.value
        else:
            audit.close()
            raise RuntimeError("audit acceptance bridge requires the deterministic inline adapter")
        run = persist_audit(session, business, request, result)
        session.commit()
        session.refresh(run)
        job.status = "succeeded"
        job.payload = {
            **job.payload,
            "result": {
                "audit_run_id": str(run.id),
                "status": run.status,
                "finding_count": len(result.findings),
            },
        }
        session.commit()
        return {"job_id": str(job.id), "status": job.status, "result": job.payload["result"]}

    app_module.publish_job = publish_job
    try:
        yield
    finally:
        app_module.publish_job = original_publish_job
