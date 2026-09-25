"""Thin REST adapter; upstream scraper implementation is intentionally not vendored."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime

import httpx
from lboe_domain import CandidateBusiness, DiscoveryRequest, DiscoveryValidationError


class MapsScraperError(RuntimeError):
    """A safe, provider-neutral discovery failure."""


class MapsScraperAdapter:
    source_name = "maps_scraper"

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        enabled: bool = False,
        kill_switch: bool = False,
        poll_interval_seconds: float = 2.0,
        max_concurrency: int = 1,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled
        self.kill_switch = kill_switch
        self.poll_interval_seconds = poll_interval_seconds
        self._semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 2)))
        self._client = client

    async def discover(self, request: DiscoveryRequest) -> list[CandidateBusiness]:
        if not self.enabled or self.kill_switch:
            raise MapsScraperError("maps scraper adapter is disabled by feature flag or kill switch")
        if request.latitude is None or request.longitude is None:
            location = request.geography or "no geography supplied"
            raise DiscoveryValidationError(
                f"maps discovery requires resolved latitude and longitude; geography={location!r} was not resolved"
            )
        async with self._semaphore:
            client = self._client or httpx.AsyncClient(timeout=request.timeout_seconds)
            close_client = self._client is None
            try:
                return await self._discover(client, request)
            except (httpx.HTTPError, TimeoutError) as exc:
                raise MapsScraperError(f"maps scraper request failed: {type(exc).__name__}") from exc
            finally:
                if close_client:
                    await client.aclose()

    async def _discover(self, client: httpx.AsyncClient, request: DiscoveryRequest) -> list[CandidateBusiness]:
        body = {
            "name": f"lboe-{request.campaign_id}",
            "keywords": request.queries,
            "lang": "en",
            # Upstream depth means scrape depth/pages, not a row limit. Keep it
            # conservative and cap returned normalized candidates separately.
            "zoom": 15,
            "lat": str(request.latitude),
            "lon": str(request.longitude),
            "fast_mode": False,
            "radius": 10000,
            "depth": 5,
            "max_time": int(request.timeout_seconds),
            "email": False,
        }
        response = await client.post(f"{self.base_url}/api/v1/jobs", json=body)
        response.raise_for_status()
        job_id = response.json().get("id")
        if not job_id:
            raise MapsScraperError("scraper did not return a job id")

        deadline = asyncio.get_running_loop().time() + request.timeout_seconds
        while True:
            if asyncio.get_running_loop().time() >= deadline:
                raise MapsScraperError("maps scraper job timed out")
            status_response = await client.get(f"{self.base_url}/api/v1/jobs/{job_id}")
            status_response.raise_for_status()
            status_body = status_response.json()
            job_status = str(status_body.get("Status", status_body.get("status", ""))).casefold()
            if job_status in {"ok", "complete", "completed", "done"}:
                break
            if job_status in {"failed", "error", "cancelled", "canceled"}:
                raise MapsScraperError("maps scraper job failed")
            await asyncio.sleep(min(self.poll_interval_seconds, max(0.1, deadline - asyncio.get_running_loop().time())))

        result = await client.get(f"{self.base_url}/api/v1/jobs/{job_id}/download")
        result.raise_for_status()
        return normalize_scraper_rows(result.text, source_ref=f"{self.base_url}/api/v1/jobs/{job_id}")[
            : request.max_results
        ]


def normalize_scraper_rows(csv_text: str, source_ref: str) -> list[CandidateBusiness]:
    """Keep only discovery fields and attach a provenance envelope per row."""
    rows = csv.DictReader(io.StringIO(csv_text))
    observed_at = datetime.now(UTC)
    candidates: list[CandidateBusiness] = []
    for row in rows:
        name = (row.get("title") or row.get("name") or "").strip()
        if not name:
            continue
        source_id = (row.get("place_id") or row.get("id") or "").strip() or None
        candidates.append(
            CandidateBusiness(
                source="maps_scraper",
                source_id=source_id,
                display_name=name,
                category=(row.get("category") or None),
                address_text=(row.get("address") or None),
                phone=(row.get("phone") or None),
                website=(row.get("website") or None),
                observed_at=observed_at,
                confidence=0.75,
                provenance={
                    "source_type": "scraper",
                    "source_ref": source_ref,
                    "storage_policy": "persistent",
                    "observed_at": observed_at.isoformat(),
                },
            )
        )
    return candidates
