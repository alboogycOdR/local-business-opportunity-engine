from __future__ import annotations

import asyncio
import importlib
import sys
import uuid
from pathlib import Path
from typing import Any

import lboe_api.main as api
from fastapi.testclient import TestClient
from lboe_api.db import Job
from sqlalchemy.orm import Session, sessionmaker

# The worker is a sibling package in this monorepo; make its actual consumer available to this focused test.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "worker" / "src"))


def test_worker_terminal_result_is_persisted_and_duplicate_delivery_is_noop() -> None:
    worker_module = importlib.import_module("lboe_worker.worker")
    worker_class = worker_module.JobWorker
    with TestClient(api.app):
        job_id = uuid.uuid4()
        with api.SessionLocal() as session:
            session.add(
                Job(
                    id=job_id,
                    idempotency_key=f"audit-test:{job_id}",
                    job_type="DISCOVER_CAMPAIGN",
                    status="queued",
                    payload={"queries": ["salon"]},
                )
            )
            session.commit()

        calls = 0

        async def handler(_session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {"imported": 2, "duplicates": 1}

        worker = worker_class(
            sessionmaker(bind=api.engine, expire_on_commit=False), object(), {"DISCOVER_CAMPAIGN": handler}
        )
        asyncio.run(worker.process(str(job_id)))
        asyncio.run(worker.process(str(job_id)))

        with api.SessionLocal() as session:
            result = session.get(Job, job_id)
            assert result is not None
            assert result.status == "succeeded"
            assert result.payload["result"] == {"imported": 2, "duplicates": 1}
        assert calls == 1

        with TestClient(api.app) as client:
            response = client.get(f"/v1/jobs/{job_id}")
            assert response.status_code == 200
            assert response.json()["result"] == {"imported": 2, "duplicates": 1}
