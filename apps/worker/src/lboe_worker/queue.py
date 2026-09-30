"""Small Redis Streams transport; PostgreSQL remains the durable job record."""

from __future__ import annotations

import json
from typing import Any

from redis import Redis

STREAM = "lboe:jobs:v1"
GROUP = "lboe-workers"
RECONCILE_KEY_PREFIX = "lboe:jobs:reconciled:v1:"


def enqueue(redis: Redis, job_id: str) -> str:
    """Publish a committed PostgreSQL job ID; no business payload is copied to Redis."""
    return str(redis.xadd(STREAM, {"job_id": job_id}))


def reconcile_key(job_id: str) -> str:
    """Short-lived Redis marker that bounds duplicate recovery publications."""
    return f"{RECONCILE_KEY_PREFIX}{job_id}"


def decode_message(fields: dict[Any, Any]) -> str:
    value = fields.get("job_id", fields.get(b"job_id"))
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str) or not value:
        raise ValueError("queue_message_missing_job_id")
    return value


def encode_result(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
