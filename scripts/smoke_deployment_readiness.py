"""Check safe deployment/readiness signals without exposing secrets."""

from __future__ import annotations

import argparse
import json

import httpx


def run(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=15, follow_redirects=False) as c:
        health = c.get("/health")
        ready = c.get("/ready")
        system = c.get("/v1/system/status")
        ui = c.get("/ui")
        health.raise_for_status()
        ready.raise_for_status()
        system.raise_for_status()
        payload = system.json()
        assert payload["system_delivery_count"] == 0
        assert payload["safety"]["credentials_stored"] is False
        return {"health": health.json(), "ready": ready.json(), "system_status": payload, "ui_status": ui.status_code}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
