from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from lboe_api.db import Base, Campaign, Job, make_engine
from lboe_worker.queue import decode_message
from lboe_worker.worker import JobWorker
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class FakeRedis:
    def __init__(self) -> None:
        self.acked: list[Any] = []
        self.messages: list[tuple[str, dict[bytes, bytes]]] = []
        self.published: list[tuple[str, dict[str, str]]] = []
        self.keys: set[str] = set()

    async def xreadgroup(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        if not self.messages:
            return []
        return [(b"lboe:jobs:v1", [self.messages.pop(0)])]

    async def xack(self, _stream: str, _group: str, message_id: Any) -> None:
        self.acked.append(message_id)

    async def set(self, key: str, _value: str, *, nx: bool, ex: int) -> bool:
        assert nx is True
        assert ex >= 60
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    async def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self.published.append((stream, fields))
        return "1-0"

    async def delete(self, key: str) -> None:
        self.keys.discard(key)


@pytest.fixture
def sessions() -> Generator[sessionmaker[Session], None, None]:
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def add_job(sessions: sessionmaker[Session], job_type: str = "TEST") -> Job:
    with sessions() as session:
        campaign = Campaign(name="worker-test", vertical="salon", geography="test")
        session.add(campaign)
        session.flush()
        job = Job(idempotency_key=str(uuid.uuid4()), job_type=job_type, status="queued", payload={"x": 1})
        session.add(job)
        session.commit()
        return job


def get_job(sessions: sessionmaker[Session], job_id: uuid.UUID) -> Job:
    with sessions() as session:
        return session.scalar(select(Job).where(Job.id == job_id))  # type: ignore[return-value]


def test_success_stores_result_and_redelivery_does_not_repeat(sessions: sessionmaker[Session]) -> None:
    job = add_job(sessions)
    called = 0

    async def handler(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called += 1
        return {"seen": payload["x"]}

    worker = JobWorker(sessions, FakeRedis(), {"TEST": handler})
    asyncio.run(worker.process(str(job.id)))
    asyncio.run(worker.process(str(job.id)))

    stored = get_job(sessions, job.id)
    assert stored.status == "succeeded"
    assert stored.payload["result"] == {"seen": 1}
    assert called == 1


def test_failure_is_persisted_and_not_retried(sessions: sessionmaker[Session]) -> None:
    job = add_job(sessions)
    called = 0

    async def handler(_session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called += 1
        raise RuntimeError("secret provider details must not be persisted")

    worker = JobWorker(sessions, FakeRedis(), {"TEST": handler})
    asyncio.run(worker.process(str(job.id)))
    asyncio.run(worker.process(str(job.id)))

    stored = get_job(sessions, job.id)
    assert stored.status == "failed"
    assert stored.payload["error"] == "RuntimeError"
    assert "secret" not in str(stored.payload)
    assert called == 1


def test_queue_message_contains_only_job_identifier() -> None:
    assert decode_message({b"job_id": b"job-123"}) == "job-123"
    with pytest.raises(ValueError, match="queue_message_missing_job_id"):
        decode_message({b"payload": b"private prospect data"})


def test_reconciler_republishes_only_aged_queued_jobs_once(sessions: sessionmaker[Session]) -> None:
    aged = add_job(sessions)
    fresh = add_job(sessions)
    terminal = add_job(sessions)
    with sessions() as session:
        session.get(Job, aged.id).created_at = datetime.now(UTC) - timedelta(minutes=5)  # type: ignore[union-attr]
        session.get(Job, terminal.id).created_at = datetime.now(UTC) - timedelta(minutes=5)  # type: ignore[union-attr]
        session.get(Job, terminal.id).status = "succeeded"  # type: ignore[union-attr]
        session.commit()

    redis = FakeRedis()
    worker = JobWorker(sessions, redis, {}, reconcile_grace_seconds=30)
    assert asyncio.run(worker.reconcile_queued_jobs()) == 1
    assert asyncio.run(worker.reconcile_queued_jobs()) == 0
    assert redis.published == [("lboe:jobs:v1", {"job_id": str(aged.id)})]
    assert str(fresh.id) not in str(redis.published)
    assert str(terminal.id) not in str(redis.published)
