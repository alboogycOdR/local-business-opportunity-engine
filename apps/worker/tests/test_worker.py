from __future__ import annotations

import asyncio
import uuid
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

    async def xreadgroup(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        if not self.messages:
            return []
        return [(b"lboe:jobs:v1", [self.messages.pop(0)])]

    async def xack(self, _stream: str, _group: str, message_id: Any) -> None:
        self.acked.append(message_id)


@pytest.fixture
def sessions() -> sessionmaker[Session]:
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
