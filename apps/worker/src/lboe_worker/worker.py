"""At-most-once job execution guarded by the PostgreSQL jobs row."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from lboe_api.audit_service import execute_audit
from lboe_api.config import Settings
from lboe_api.db import Business, Job, make_engine
from lboe_api.enrichment_service import execute_enrichment
from lboe_domain import AuditRequest, DiscoveryRequest, EnrichmentRequest
from lboe_maps_scraper import MapsScraperAdapter
from lboe_website_auditor import PlaywrightAuditAdapter
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .queue import GROUP, STREAM, decode_message

logger = logging.getLogger("lboe.worker")
Handler = Callable[[Session, dict[str, Any]], Awaitable[dict[str, Any]]]


class JobWorker:
    """Processes queue references once; failed or interrupted jobs are never auto-retried."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        redis: Any,
        handlers: dict[str, Handler],
        *,
        consumer: str = "worker-1",
        heartbeat_path: str | None = None,
    ) -> None:
        self.sessions = sessions
        self.redis = redis
        self.handlers = handlers
        self.consumer = consumer
        self.heartbeat_path = heartbeat_path

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run_once(self, block_ms: int = 1000) -> bool:
        rows = await self.redis.xreadgroup(GROUP, self.consumer, {STREAM: ">"}, count=1, block=block_ms)
        if not rows:
            self._touch_heartbeat()
            return False
        _, messages = rows[0]
        for message_id, fields in messages:
            try:
                job_id = decode_message(fields)
                await self.process(job_id)
            except Exception:
                logger.exception("queue_message_failed")
            finally:
                # Acknowledged failures stay failed in PostgreSQL; they are not requeued.
                await self.redis.xack(STREAM, GROUP, message_id)
                self._touch_heartbeat()
        return True

    async def process(self, job_id: str) -> None:
        try:
            parsed_id = uuid.UUID(job_id)
        except ValueError as exc:
            raise ValueError("job_id_invalid") from exc

        # Claim by committing running before executing side effects. A redelivered message
        # observes running/succeeded/failed and exits instead of repeating work.
        with self.sessions() as session:
            job = session.scalar(select(Job).where(Job.id == parsed_id).with_for_update())
            if job is None:
                raise LookupError("job_not_found")
            if job.status != "queued":
                return
            job.status = "running"
            session.commit()
            job_type = job.job_type
            payload = dict(job.payload)

        try:
            handler = self.handlers.get(job_type)
            if handler is None:
                raise ValueError("job_type_unsupported")
            with self.sessions() as session:
                result = await handler(session, payload)
            with self.sessions() as session:
                job = session.scalar(select(Job).where(Job.id == parsed_id).with_for_update())
                if job is not None and job.status == "running":
                    job.status = "succeeded"
                    job.payload = {**job.payload, "result": result}
                    session.commit()
        except Exception as exc:
            with self.sessions() as session:
                job = session.scalar(select(Job).where(Job.id == parsed_id).with_for_update())
                if job is not None and job.status == "running":
                    job.status = "failed"
                    # Store the safe exception class only, never provider payloads or contact data.
                    job.payload = {**job.payload, "error": type(exc).__name__}
                    session.commit()
            logger.exception("job_execution_failed", extra={"job_id": job_id, "job_type": job_type})

    def _touch_heartbeat(self) -> None:
        if self.heartbeat_path:
            from pathlib import Path

            path = Path(self.heartbeat_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()


async def _discover(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from lboe_api.discovery_service import execute_discovery

    request = DiscoveryRequest.model_validate(payload)
    settings = Settings()
    adapter = MapsScraperAdapter(
        base_url=settings.maps_scraper_url,
        enabled=settings.maps_scraper_enabled,
        kill_switch=settings.discovery_kill_switch,
        poll_interval_seconds=settings.discovery_poll_interval_seconds,
        max_concurrency=1,
    )
    result = await execute_discovery(session, adapter, request)
    return result


async def _audit(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    business_id = uuid.UUID(str(payload["business_id"]))
    business = session.get(Business, business_id)
    if business is None:
        raise ValueError("business_not_found")
    request = AuditRequest.model_validate(payload)
    settings = Settings()
    adapter = PlaywrightAuditAdapter(settings.audit_artifact_root, max_concurrency=1)
    run, result = await execute_audit(session, adapter, business, request)
    return {"audit_run_id": str(run.id), "status": run.status, "finding_count": len(result.findings)}


async def _enrich(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    request = EnrichmentRequest.model_validate(payload)
    run, result = await execute_enrichment(session, request)
    return {"enrichment_run_id": str(run.id), "status": result.status, "fact_count": len(result.facts)}


async def serve() -> None:
    settings = Settings()
    engine = make_engine(settings.database_url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    worker = JobWorker(
        sessions,
        redis,
        {"DISCOVER_CAMPAIGN": _discover, "AUDIT_WEBSITE": _audit, "ENRICH_BUSINESS": _enrich},
        consumer=os.getenv("LBOE_WORKER_NAME", f"worker-{os.getpid()}"),
        heartbeat_path=os.getenv("LBOE_WORKER_HEARTBEAT", "/tmp/lboe-worker-heartbeat"),
    )
    await worker.ensure_group()
    try:
        while True:
            await worker.run_once(block_ms=1000)
    finally:
        await redis.aclose()
        engine.dispose()


def main() -> None:
    logging.basicConfig(level=os.getenv("LBOE_LOG_LEVEL", "INFO"))
    asyncio.run(serve())
