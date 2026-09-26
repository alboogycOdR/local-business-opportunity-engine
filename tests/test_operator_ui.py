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
            "/ui/campaigns",
            f"/ui/campaigns/{campaign['id']}",
            f"/ui/businesses/{business_id}",
            "/ui/reports/pilot",
            f"/ui/campaigns/{campaign['id']}/reports/pilot",
            "/ui/queues",
            "/ui/queues/demo-review",
            "/ui/operators",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "System delivery is disabled" in response.text


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
