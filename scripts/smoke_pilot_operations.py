"""Exercise the Sprint 14 pilot operations console without external effects."""

from __future__ import annotations

import argparse
import json

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url.rstrip("/"), follow_redirects=False, timeout=30) as c:
        assert c.get("/ui/pilots").status_code == 200
        campaign = c.post(
            "/v1/campaigns",
            json={"name": "Sprint 15 Pilot", "vertical": "hair_salon", "geography": "Cape Town, South Africa"},
        ).json()
        imported = c.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "records": [
                    {"display_name": "Sprint 15 Synthetic Salon", "category": "hair salon", "locality": "Cape Town"}
                ],
            },
        ).json()
        assert imported["successes"]
        operator = c.post(
            "/ui/operators", data={"display_name": "Sprint 15 Operator", "role": "owner"}, follow_redirects=False
        )
        assert operator.status_code == 303
        response = c.post(
            "/ui/pilots",
            data={
                "name": "Sprint 15 Pilot",
                "campaign_id": campaign["id"],
                "mode": "dry_run",
                "target_lead_count": "10",
                "max_businesses": "50",
                "daily_demo_cap": "10",
                "daily_preview_link_cap": "10",
                "daily_manual_contact_cap": "5",
                "daily_readiness_approval_cap": "5",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        pilot_id = response.headers["location"].rsplit("/", 1)[-1]
        assert c.post(f"/ui/pilots/{pilot_id}/mark-ready", follow_redirects=False).status_code == 409
        assert (
            c.post(
                f"/ui/pilots/{pilot_id}/acknowledge-source-policy",
                data={"acknowledgement_text": "I acknowledge the pilot source policy."},
                follow_redirects=False,
            ).status_code
            == 303
        )
        assert c.post(f"/ui/pilots/{pilot_id}/mark-ready", follow_redirects=False).status_code == 303
        assert c.post(f"/ui/pilots/{pilot_id}/activate", follow_redirects=False).status_code == 303
        assert c.post(f"/ui/pilots/{pilot_id}/exports/generate", follow_redirects=False).status_code == 303
        assert (
            c.post(
                f"/ui/pilots/{pilot_id}/retrospective",
                data={"what_worked": "Synthetic rehearsal"},
                follow_redirects=False,
            ).status_code
            == 303
        )
        report = c.get(f"/v1/campaigns/{campaign['id']}/reports/pilot").json()
        delivery = next(item["count"] for item in report["quality_metrics"] if item["code"] == "system_delivery_count")
        assert delivery == 0
        print(
            json.dumps(
                {"campaign_id": campaign["id"], "pilot_id": pilot_id, "system_delivery_count": delivery}, indent=2
            )
        )


if __name__ == "__main__":
    main()
