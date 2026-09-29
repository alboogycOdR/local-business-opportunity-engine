import uuid

import lboe_api.main as api
import pytest
from fastapi.testclient import TestClient
from lboe_api.db import Job
from sqlalchemy import select


class FakeRedis:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.fail = False

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        if self.fail:
            raise ConnectionError("redis unavailable")
        assert stream == "lboe:jobs:v1"
        self.messages.append(fields)
        return str(len(self.messages))

    def close(self) -> None:
        return None


def test_discovery_publishes_only_committed_job_id_and_retries_idempotently(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("lboe_api.main.Redis.from_url", lambda *args, **kwargs: redis)
    with TestClient(api.app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "Queue test", "vertical": "salon"}).json()["id"]
        payload = {"queries": ["salon"], "idempotency_key": "queue-test-1"}
        first = client.post(f"/v1/campaigns/{campaign_id}/discover", json=payload)
        assert first.status_code == 202
        job_id = first.json()["job_id"]
        assert first.json()["status"] == "queued"
        assert redis.messages == [{"job_id": job_id}]

        second = client.post(f"/v1/campaigns/{campaign_id}/discover", json=payload)
        assert second.status_code == 202
        assert second.json()["job_id"] == job_id
        assert all(set(message) == {"job_id"} for message in redis.messages)

        status = client.get(f"/v1/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json() == {
            "job_id": job_id,
            "job_type": "DISCOVER_CAMPAIGN",
            "status": "queued",
            "result": None,
            "error": None,
        }


def test_redis_failure_leaves_authoritative_queued_job_for_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    redis.fail = True
    monkeypatch.setattr("lboe_api.main.Redis.from_url", lambda *args, **kwargs: redis)
    with TestClient(api.app) as client:
        campaign_id = client.post("/v1/campaigns", json={"name": "Queue outage", "vertical": "salon"}).json()["id"]
        payload = {"queries": ["salon"], "idempotency_key": "queue-retry-1"}
        failed_publish = client.post(f"/v1/campaigns/{campaign_id}/discover", json=payload)
        assert failed_publish.status_code == 503
        job_id = failed_publish.json()["detail"]["job_id"]
        with api.SessionLocal() as session:
            row = session.scalar(select(Job).where(Job.id == uuid.UUID(job_id)))
            assert row is not None and row.status == "queued"

        redis.fail = False
        retried = client.post(f"/v1/campaigns/{campaign_id}/discover", json=payload)
        assert retried.status_code == 202
        assert retried.json()["job_id"] == job_id
        assert redis.messages == [{"job_id": job_id}]
