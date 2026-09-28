"""Run a synthetic proposal generation, review, and export smoke test."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import httpx


def call(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def run(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=30) as c:
        campaign = call(
            c,
            "POST",
            "/v1/campaigns",
            json={"name": "Proposal Smoke", "vertical": "hair_salon", "geography": "Cape Town"},
        )
        imported = call(
            c,
            "POST",
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "source_type": "manual",
                "records": [
                    {
                        "display_name": "Synthetic Proposal Salon",
                        "category": "hair salon",
                        "locality": "Cape Town",
                        "address_text": "Synthetic Cape Town",
                    }
                ],
            },
        )
        business_id = imported["successes"][0]["business_id"]
        for state in ("DEDUPED", "QUALIFIED", "ENRICHING", "ENRICHED", "AUDITING", "AUDITED", "SCORED"):
            call(
                c,
                "POST",
                f"/v1/businesses/{business_id}/transition",
                json={"to_state": state, "actor": "proposal-smoke"},
            )
        seed_prerequisites(business_id)
        call(c, "GET", f"/v1/businesses/{business_id}/demos")
        proposal = call(
            c,
            "POST",
            f"/v1/businesses/{business_id}/proposal",
            json={"operator_requested": True, "idempotency_key": "proposal-smoke"},
        )
        assert proposal["id"]
        fetched = call(c, "GET", f"/v1/proposals/{proposal['id']}")
        reviewed = call(
            c,
            "POST",
            f"/v1/proposals/{proposal['id']}/review",
            json={"decision": "approve", "reviewer": "proposal-smoke"},
        )
        exported = call(c, "POST", f"/v1/proposals/{proposal['id']}/export")
        files = exported["export"]
        expected = {
            "proposal.md",
            "proposal-summary.json",
            "proposal-sections.json",
            "proposal-line-items.csv",
            "proposal-evidence.json",
        }
        assert expected == {Path(value).name for value in files.values()}
        forbidden = ("authorization", "password", "secret", "raw scraper", "preview token")
        for value in files.values():
            text = Path(value).read_text(encoding="utf-8").lower()
            assert not any(item in text for item in forbidden)
        return {
            "business_id": business_id,
            "proposal_id": proposal["id"],
            "proposal_status": reviewed["status"],
            "export_files": sorted(expected),
            "system_delivery_count": 0,
            "fetched": fetched["id"],
        }


def seed_prerequisites(business_id: str) -> None:
    """Seed synthetic score, brief, approved demo, and QA rows."""
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps" / "api" / "src"))
    from lboe_api.db import (  # noqa: PLC0415
        Business,
        BusinessBrief,
        DemoQaRun,
        GeneratedDemo,
        GeneratedDemoClaim,
        OpportunityScore,
        make_session_factory,
    )

    database_url = os.getenv("LBOE_DATABASE_URL") or "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
    session = make_session_factory(database_url)()
    business = session.get(Business, uuid.UUID(business_id))
    assert business is not None
    score = OpportunityScore(
        business_id=business.id,
        version="opportunity-v1",
        score=84,
        band="high",
        recommended_next_action="generate_demo",
    )
    session.add(score)
    session.flush()
    brief = BusinessBrief(
        business_id=business.id,
        score_id=score.id,
        version="brief-v1",
        summary="Synthetic proposal facts.",
        recommended_next_action="generate_demo",
        confidence=0.95,
    )
    session.add(brief)
    session.flush()
    demo = GeneratedDemo(
        business_id=business.id,
        brief_id=brief.id,
        score_id=score.id,
        version="demo-v1",
        demo_type="starter_website",
        status="approved",
        preview_path=str(root / "artifacts" / "demos" / "synthetic" / "index.html"),
    )
    session.add(demo)
    session.flush()
    session.add(
        GeneratedDemoClaim(
            demo_id=demo.id,
            claim_text="Independent concept preview",
            claim_type="disclaimer",
            evidence={"synthetic": True},
            confidence=1.0,
            approved=True,
        )
    )
    session.add(DemoQaRun(demo_id=demo.id, status="passed", checks={"synthetic": True}))
    session.commit()
    session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
