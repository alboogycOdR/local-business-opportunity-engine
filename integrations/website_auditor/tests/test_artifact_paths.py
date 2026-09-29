from __future__ import annotations

import uuid

from lboe_website_auditor.playwright_auditor import PlaywrightAuditAdapter


def test_audit_artifact_paths_are_unique_per_run(tmp_path) -> None:
    adapter = PlaywrightAuditAdapter(str(tmp_path))
    business_id = uuid.uuid4()
    first = adapter.artifact_directory(business_id, uuid.uuid4())
    second = adapter.artifact_directory(business_id, uuid.uuid4())

    assert first.parent == second.parent == tmp_path / str(business_id)
    assert first != second
    assert first.name != second.name
