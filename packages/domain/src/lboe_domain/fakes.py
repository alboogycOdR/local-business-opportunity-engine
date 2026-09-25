"""Deterministic adapters used by tests and local development."""

from __future__ import annotations

from lboe_domain.discovery import CandidateBusiness, DiscoveryRequest


class FakeDiscoveryAdapter:
    def __init__(self, candidates: list[CandidateBusiness] | None = None, error: Exception | None = None) -> None:
        self.candidates = candidates or []
        self.error = error
        self.calls = 0

    async def discover(self, request: DiscoveryRequest) -> list[CandidateBusiness]:
        self.calls += 1
        if self.error:
            raise self.error
        return self.candidates[: request.max_results]
