from pathlib import Path
from typing import Any
from uuid import uuid4

from lboe_api.demo_generator import qa_demo, render_demo, write_artifacts


class Business:
    id = uuid4()
    display_name = "Test Salon"
    category = "hair salon"
    locality = "Cape Town"


def brief(action: str = "generate_demo") -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "facts": {
            "identity": [
                {"label": "Business name", "value": "Test Salon"},
                {"label": "Category", "value": "hair salon"},
            ]
        },
        "recommended_action": {"code": action},
    }


def test_static_demo_artifacts_and_qa(tmp_path: Path) -> None:
    rendered = render_demo(uuid4(), Business(), brief(), "starter_website")
    demo_id = uuid4()
    rows = write_artifacts(tmp_path, demo_id, rendered)
    status, checks = qa_demo(tmp_path, demo_id, rendered)
    assert status == "passed"
    assert all(checks.values())
    assert {row["kind"] for row in rows} == {"index", "styles", "metadata"}
    assert "Not the official website" in (tmp_path / "demos" / str(demo_id) / "index.html").read_text()


def test_qa_rejects_prohibited_copy(tmp_path: Path) -> None:
    rendered = render_demo(uuid4(), Business(), brief(), "starter_website")
    demo_id = uuid4()
    write_artifacts(tmp_path, demo_id, rendered)
    path = tmp_path / "demos" / str(demo_id) / "index.html"
    path.write_text(path.read_text() + " Best salon in Cape Town", encoding="utf-8")
    status, checks = qa_demo(tmp_path, demo_id, rendered)
    assert status == "failed"
    assert checks["prohibited_phrases_absent"] is False


def test_claim_without_evidence_is_rejected(tmp_path: Path) -> None:
    rendered = render_demo(uuid4(), Business(), brief(), "starter_website")
    rendered.claims[0].evidence = {}
    rendered.claims[0].claim_type = "verified"
    demo_id = uuid4()
    write_artifacts(tmp_path, demo_id, rendered)
    status, checks = qa_demo(tmp_path, demo_id, rendered)
    assert status == "failed"
    assert checks["claims_have_evidence"] is False
