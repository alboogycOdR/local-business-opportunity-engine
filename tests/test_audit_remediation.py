from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import lboe_api.main as api
import pytest
from fastapi.testclient import TestClient
from lboe_api.config import Settings, production_security_errors
from lboe_api.db import Job, Operator, OperatorSession
from lboe_api.password_auth import hash_password, verify_password
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

# The worker is a sibling package in this monorepo; make its actual consumer available to this focused test.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "worker" / "src"))


def test_operator_navigation_has_compact_mobile_disclosure() -> None:
    with TestClient(api.app) as client:
        response = client.get("/ui")
    assert response.status_code == 200
    assert "<details class='mobile-nav'><summary>Menu</summary>" in response.text
    assert "class='desktop-nav' aria-label='Primary'" in response.text


def test_enabled_operator_auth_requires_bearer_for_versioned_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.settings, "auth_enabled", True)
    monkeypatch.setattr(api.settings, "operator_auth_token", "test-operator-token")
    job_id = uuid.uuid4()
    with TestClient(api.app) as client:
        denied = client.get(f"/v1/jobs/{job_id}")
        allowed = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": "Bearer test-operator-token"})
        health = client.get("/health")

    assert denied.status_code == 401
    assert allowed.status_code == 404
    assert health.status_code == 200


def test_production_security_configuration_fails_closed() -> None:
    unsafe = Settings(environment="production")
    errors = production_security_errors(unsafe)
    assert len(errors) == 7
    assert any("LBOE_AUTH_ENABLED" in error for error in errors)
    assert any("LBOE_AUTH_SECRET" in error for error in errors)

    safe = Settings(
        environment="production",
        auth_enabled=True,
        operator_auth_token="t" * 32,
        auth_secret="s" * 32,
        secure_cookies=True,
        csrf_enabled=True,
        operator_username="admin",
        operator_password_hash=hash_password("a-secure-test-password"),
    )
    assert production_security_errors(safe) == []


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("a-secure-test-password")
    second = hash_password("a-secure-test-password")
    assert first != second
    assert first.startswith("scrypt:")
    assert verify_password("a-secure-test-password", first)
    assert not verify_password("wrong-password", first)


def test_username_password_login_and_remember_me(monkeypatch: pytest.MonkeyPatch) -> None:
    username = f"operator-{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(api.settings, "auth_enabled", True)
    monkeypatch.setattr(api.settings, "csrf_enabled", False)
    monkeypatch.setattr(api.settings, "secure_cookies", False)
    with api.SessionLocal() as db:
        operator = Operator(
            display_name="Login Test",
            username=username,
            password_hash=hash_password("a-secure-test-password"),
        )
        db.add(operator)
        db.commit()
        operator_id = operator.id

    with TestClient(api.app) as client:
        denied = client.post(
            "/ui/login", data={"username": username, "password": "wrong-password"}, follow_redirects=False
        )
        response = client.post(
            "/ui/login",
            data={"username": username.upper(), "password": "a-secure-test-password", "remember_me": "true"},
            follow_redirects=False,
        )
        dashboard = client.get("/ui")

    assert denied.status_code == 401
    assert "username or password is incorrect" in denied.text
    assert response.status_code == 303
    assert "Max-Age=2592000" in response.headers.get_list("set-cookie")[0]
    assert dashboard.status_code == 200
    with api.SessionLocal() as db:
        created = db.scalar(
            select(OperatorSession)
            .where(OperatorSession.operator_id == operator_id)
            .order_by(OperatorSession.created_at.desc())
        )
        assert created is not None
        assert created.expires_at - created.created_at > timedelta(days=29)


def test_enabled_ui_csrf_rejects_cross_origin_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "csrf-test-secret"
    session_token = "opaque-session-token"
    csrf_token = "opaque-csrf-token"
    monkeypatch.setattr(api.settings, "auth_enabled", True)
    monkeypatch.setattr(api.settings, "csrf_enabled", True)
    monkeypatch.setattr(api.settings, "auth_secret", secret)
    with api.SessionLocal() as db:
        operator = Operator(display_name="Test operator")
        db.add(operator)
        db.flush()
        db.add(
            OperatorSession(
                operator_id=operator.id,
                session_hash=hmac.new(secret.encode(), session_token.encode(), hashlib.sha256).hexdigest(),
                csrf_hash=hashlib.sha256(csrf_token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        db.commit()

    with TestClient(api.app) as client:
        client.cookies.set("lboe_session", session_token)
        client.cookies.set("lboe_csrf", csrf_token)
        cross_origin = client.post("/ui/logout", headers={"Origin": "https://attacker.example"})
        same_origin = client.post("/ui/logout", headers={"Origin": "http://testserver"}, follow_redirects=False)

    assert cross_origin.status_code == 403
    assert same_origin.status_code == 303


def test_worker_terminal_result_is_persisted_and_duplicate_delivery_is_noop() -> None:
    worker_module = importlib.import_module("lboe_worker.worker")
    worker_class = worker_module.JobWorker
    with TestClient(api.app):
        job_id = uuid.uuid4()
        with api.SessionLocal() as session:
            session.add(
                Job(
                    id=job_id,
                    idempotency_key=f"audit-test:{job_id}",
                    job_type="DISCOVER_CAMPAIGN",
                    status="queued",
                    payload={"queries": ["salon"]},
                )
            )
            session.commit()

        calls = 0

        async def handler(_session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {"imported": 2, "duplicates": 1}

        worker = worker_class(
            sessionmaker(bind=api.engine, expire_on_commit=False), object(), {"DISCOVER_CAMPAIGN": handler}
        )
        asyncio.run(worker.process(str(job_id)))
        asyncio.run(worker.process(str(job_id)))

        with api.SessionLocal() as session:
            result = session.get(Job, job_id)
            assert result is not None
            assert result.status == "succeeded"
            assert result.payload["result"] == {"imported": 2, "duplicates": 1}
        assert calls == 1

        with TestClient(api.app) as client:
            response = client.get(f"/v1/jobs/{job_id}")
            assert response.status_code == 200
            assert response.json()["result"] == {"imported": 2, "duplicates": 1}
