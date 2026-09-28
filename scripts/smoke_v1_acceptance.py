"""Representative v1 coherence smoke using synthetic records only."""

from __future__ import annotations

import argparse
import json

import httpx


def run(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=20) as c:
        for path in ("/health", "/ready", "/v1/system/status"):
            response = c.get(path)
            response.raise_for_status()
        status = c.get("/v1/system/status").json()
        assert status["system_delivery_count"] == 0
        openapi = c.get("/openapi.json")
        openapi.raise_for_status()
        paths = openapi.json().get("paths", {})
        required = (
            "/v1/businesses/{business_id}/proposal",
            "/v1/businesses/{business_id}/delivery-project",
            "/v1/system/status",
        )
        missing = [path for path in required if path not in paths]
        assert not missing, missing
        return {
            "status": "passed",
            "health": "ok",
            "ready": status["status"],
            "system_delivery_count": 0,
            "critical_paths_checked": len(required),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
