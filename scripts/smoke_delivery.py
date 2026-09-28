"""Synthetic delivery workflow smoke test; never stores credentials or sends anything."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def call(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def run(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=30) as client:
        campaign = call(
            client,
            "POST",
            "/v1/campaigns",
            json={"name": "Delivery Smoke", "vertical": "hair_salon", "geography": "Cape Town"},
        )
        imported = call(
            client,
            "POST",
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "source_type": "manual",
                "records": [
                    {
                        "display_name": "Synthetic Delivery Salon",
                        "category": "hair salon",
                        "locality": "Cape Town",
                    }
                ],
            },
        )
        business_id = imported["successes"][0]["business_id"]
        project = call(
            client,
            "POST",
            f"/v1/businesses/{business_id}/delivery-project",
            json={"operator_created": True, "title": "Synthetic delivery smoke"},
        )
        project_id = project["id"]
        call(
            client,
            "POST",
            f"/v1/delivery-projects/{project_id}/checklist",
            json={"category": "intake", "code": "business_name", "status": "verified", "notes": "Synthetic only"},
        )
        call(
            client,
            "POST",
            f"/v1/delivery-projects/{project_id}/checklist",
            json={
                "category": "access_assets",
                "code": "domain_access",
                "status": "pending",
                "notes": "Use password manager; no secret stored",
            },
        )
        call(
            client,
            "POST",
            f"/v1/delivery-projects/{project_id}/milestone",
            json={"milestone_type": "intake complete", "status": "complete", "note": "Synthetic only"},
        )
        approved = call(
            client,
            "POST",
            f"/v1/delivery-projects/{project_id}/approval",
            json={
                "approval_type": "client_approval",
                "approved_item": "Synthetic preview",
                "client_assertion": "Operator-recorded assertion; not an e-signature",
                "notes": "Synthetic only",
            },
        )
        exported = call(client, "POST", f"/v1/delivery-projects/{project_id}/export")
        files = exported["exports"][-1]["files"]
        expected = {
            "delivery-summary.json",
            "delivery-checklist.csv",
            "client-questions.md",
            "handoff-notes.md",
            "milestone-history.csv",
        }
        assert expected == {Path(path).name for path in files.values()}
        forbidden = ("password=", "secret=", "authorization:", "bearer ", "preview_token", "payment_number")
        for path in files.values():
            text = Path(path).read_text(encoding="utf-8").lower()
            assert not any(term in text for term in forbidden)
        return {
            "business_id": business_id,
            "delivery_project_id": project_id,
            "status": approved["status"],
            "export_files": sorted(expected),
            "system_delivery_count": 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
