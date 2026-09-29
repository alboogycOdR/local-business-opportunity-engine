from pathlib import Path

from fastapi.testclient import TestClient
from lboe_api.main import app


def test_operator_ui_pages_and_safety_banner() -> None:
    with TestClient(app) as client:
        campaign = client.post(
            "/v1/campaigns", json={"name": "UI Pilot", "vertical": "hair_salon", "geography": "Cape Town"}
        ).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "UI Salon", "category": "hair salon"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        for path in (
            "/ui",
            "/ui/opportunities",
            "/ui/campaigns",
            f"/ui/campaigns/{campaign['id']}",
            f"/ui/businesses/{business_id}",
            "/ui/reports/pilot",
            f"/ui/campaigns/{campaign['id']}/reports/pilot",
            "/ui/queues",
            "/ui/queues/proposal-ready",
            "/ui/queues/delivery",
            "/ui/queues/demo-review",
            "/ui/operators",
            "/ui/queues/no-demo-reason",
            "/ui/queues/qa-failed",
            "/ui/queues/not-outreach-ready",
            "/ui/queues/weak-evidence",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "System delivery is disabled" in response.text
        assert "Opportunity Cards" in client.get("/ui").text
        assert "Opportunity Cards" in client.get("/ui/opportunities").text


def test_no_website_queue_and_campaign_filter() -> None:
    with TestClient(app) as client:
        campaign = client.post(
            "/v1/campaigns", json={"name": "No Website UI", "vertical": "hair_salon", "geography": "Cape Town"}
        ).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "records": [
                    {"display_name": "No Website Salon", "category": "hair salon"},
                    {"display_name": "Website Salon", "category": "hair salon", "website": "https://example.com"},
                ],
            },
        ).json()
        no_site = client.get(f"/ui/campaigns/{campaign['id']}?website_status=no_website")
        assert no_site.status_code == 200
        assert "No Website Salon" in no_site.text
        assert ">Website Salon</a>" not in no_site.text
        queue = client.get("/ui/queues/no-website")
        assert queue.status_code == 200
        assert "No website opportunities" in queue.text
        assert imported["successes"]
        opportunities = client.get("/ui/opportunities")
        assert opportunities.status_code == 200
        assert "No Website Salon" in opportunities.text
        assert "Starter Website" in opportunities.text
        assert "View opportunity" in opportunities.text


def test_review_gap_opportunity_card_and_peer_evidence() -> None:
    from datetime import UTC, datetime

    from lboe_api.db import SourceObservation
    from lboe_api.main import SessionLocal

    with TestClient(app) as client:
        campaign = client.post(
            "/v1/campaigns", json={"name": "Review Gap UI", "vertical": "gym", "geography": "Cape Town"}
        ).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={
                "format": "json",
                "records": [
                    {"display_name": "Weak Profile Gym", "category": "gym", "locality": "Cape Town"},
                    {"display_name": "Stronger Peer Gym", "category": "gym", "locality": "Cape Town"},
                ],
            },
        ).json()
        weak_id = imported["successes"][0]["business_id"]
        peer_id = imported["successes"][1]["business_id"]
        with SessionLocal() as session:
            now = datetime.now(UTC)
            for business_id, field, value in (
                (weak_id, "rating", "3.6"),
                (weak_id, "review_count", "18"),
                (peer_id, "rating", "4.4"),
                (peer_id, "review_count", "125"),
            ):
                session.add(
                    SourceObservation(
                        business_id=__import__("uuid").UUID(business_id),
                        field=field,
                        source_type="manual_test",
                        source_ref="test-fixture",
                        observed_at=now,
                        storage_policy="persistent",
                        confidence=0.9,
                        value=value,
                    )
                )
            session.commit()
        response = client.get("/ui/opportunities")
        assert response.status_code == 200
        assert "Weak Profile Gym" in response.text
        assert "Review Gap Opportunity" in response.text
        assert "Rating: 3.6" in response.text
        assert "Reviews: 18" in response.text
        assert "Stronger Peer Gym shows 4.4 stars" in response.text
        assert "losing" not in response.text.lower()
        assert "increase revenue" not in response.text.lower()


def test_review_gap_suppression_blocks_sales_action() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "Review Safety UI", "vertical": "gym"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "Suppressed Review Gym", "category": "gym"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        client.post(f"/ui/businesses/{business_id}/suppress", data={"reason": "review safety test"})
        html = client.get("/ui/opportunities").text
        start = html.index("Suppressed Review Gym")
        card = html[start : start + 900]
        assert "No action" in card
        assert "Generate Proposal" not in card
        assert "Prepare Outreach" not in card


def test_ui_suppression_is_audited() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "UI Safety", "vertical": "salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "Suppression UI", "category": "salon"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        response = client.post(
            f"/ui/businesses/{business_id}/suppress", data={"reason": "UI test"}, follow_redirects=False
        )
        assert response.status_code == 303
        assert client.get(f"/v1/businesses/{business_id}").json()["state"] == "SUPPRESSED"


def test_local_operator_assignment_and_comment() -> None:
    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "UI Operators", "vertical": "salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "Assigned UI Salon", "category": "salon"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        created = client.post(
            "/ui/operators", data={"display_name": "Reviewer", "role": "reviewer"}, follow_redirects=False
        )
        assert created.status_code == 303
        operator_page = client.get("/ui/operators")
        assert "Reviewer" in operator_page.text
        from lboe_api.db import Operator
        from lboe_api.main import SessionLocal

        with SessionLocal() as session:
            operator = session.query(Operator).filter_by(display_name="Reviewer").first()
            assert operator is not None
            operator_id = str(operator.id)
        assigned = client.post(
            f"/ui/businesses/{business_id}/assign",
            data={"operator_id": operator_id},
            follow_redirects=False,
        )
        assert assigned.status_code == 303
        noted = client.post(
            f"/ui/businesses/{business_id}/comment",
            data={"body": "Review facts before next step."},
            follow_redirects=False,
        )
        assert noted.status_code == 303
        assert "Review facts" in client.get(f"/ui/businesses/{business_id}").text


def test_controlled_preview_token_lifecycle(tmp_path: Path) -> None:
    from lboe_api.db import Business, DemoArtifact, DemoPreviewLink, GeneratedDemo
    from lboe_api.main import SessionLocal, settings

    with TestClient(app) as client:
        campaign = client.post("/v1/campaigns", json={"name": "Preview UI", "vertical": "salon"}).json()
        imported = client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "Preview Salon", "category": "salon"}]},
        ).json()
        business_id = imported["successes"][0]["business_id"]
        with SessionLocal() as session:
            business = session.get(Business, __import__("uuid").UUID(business_id))
            assert business is not None
            demo = GeneratedDemo(
                business_id=business.id,
                brief_id=__import__("uuid").uuid4(),
                version="test",
                demo_type="starter_website",
                status="approved",
                preview_path="",
            )
            # SQLite test databases do not enforce foreign keys; use a direct
            # recorded artifact to exercise the route's path and token gates.
            session.add(demo)
            session.flush()
            artifact_dir = tmp_path / "demos" / str(demo.id)
            artifact_dir.mkdir(parents=True)
            artifact = artifact_dir / "index.html"
            artifact.write_text(
                "<html><body>Concept preview prepared independently for demonstration. "
                "Not the official website of this business.</body></html>",
                encoding="utf-8",
            )
            session.add(
                DemoArtifact(
                    demo_id=demo.id,
                    kind="index",
                    path=str(artifact),
                    mime_type="text/html",
                    byte_size=artifact.stat().st_size,
                )
            )
            session.commit()
            demo_id = str(demo.id)
        old_root = settings.demo_artifact_root
        settings.demo_artifact_root = str(tmp_path)
        try:
            response = client.post(f"/ui/demos/{demo_id}/preview-links", data={"label": "Test", "expires_days": "1"})
            assert response.status_code == 200
            token = response.text.split("/preview/", 1)[1].split("</code>", 1)[0]
            preview = client.get(f"/preview/{token}")
            assert preview.status_code == 200
            assert "Not the official website" in preview.text
            with SessionLocal() as session:
                link = session.query(DemoPreviewLink).filter_by(demo_id=__import__("uuid").UUID(demo_id)).first()
                assert link is not None
                assert token not in link.token_hash
                link_id = str(link.id)
            revoked = client.post(f"/ui/preview-links/{link_id}/revoke", follow_redirects=False)
            assert revoked.status_code == 303
            assert client.get(f"/preview/{token}").status_code == 410
        finally:
            settings.demo_artifact_root = old_root


def test_pilot_console_config_readiness_and_retrospective() -> None:
    with TestClient(app) as client:
        campaign = client.post(
            "/v1/campaigns", json={"name": "V5 Pilot", "vertical": "salon", "geography": "Cape Town"}
        ).json()
        client.post(
            f"/v1/campaigns/{campaign['id']}/import",
            json={"format": "json", "records": [{"display_name": "V5 Salon", "category": "salon"}]},
        )
        response = client.post(
            "/ui/pilots",
            data={
                "name": "V5 Console",
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
        assert client.get(f"/ui/pilots/{pilot_id}").status_code == 200
        assert "DRY RUN MODE" in client.get(f"/ui/pilots/{pilot_id}").text
        assert client.get(f"/ui/pilots/{pilot_id}/readiness").status_code == 200
        assert client.get(f"/ui/pilots/{pilot_id}/calibration").status_code == 200
        ack = client.post(
            f"/ui/pilots/{pilot_id}/acknowledge-source-policy",
            data={"acknowledgement_text": "I acknowledge the source policy."},
            follow_redirects=False,
        )
        assert ack.status_code == 303
        assert (
            client.post(
                f"/ui/pilots/{pilot_id}/retrospective", data={"what_worked": "clear queues"}, follow_redirects=False
            ).status_code
            == 303
        )
