import pytest
from conftest import seed_request_log
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import settings
from app.gateway.service.lifecycle import lifespan
from app.models.protocols import RequestLogLifecycleStatus


@pytest.fixture
def client(app_state):
    app = create_app(state=app_state)
    app.router.lifespan_context = lifespan
    return TestClient(app, raise_server_exceptions=False)


def test_startup_recovers_running_logs_and_shutdown_closes_clients(client, app_state):
    orphan = seed_request_log(
        app_state,
        success=False,
        status_code=None,
        lifecycle_status=RequestLogLifecycleStatus.STREAMING,
    )
    with client:
        login = client.post(
            "/api/admin/session", json={"username": "admin", "password": "password"}
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        log = client.get(f"/api/admin/request-logs/{orphan.id}", headers=headers)
        assert log.status_code == 200, log.text
        assert log.json()["lifecycle_status"] == "failed"
        assert log.json()["success"] is False
        jobs = client.get("/api/admin/cronjobs", headers=headers)
        assert jobs.status_code == 200, jobs.text
        assert jobs.json()
    assert app_state.http.is_closed


def test_failed_startup_closes_clients(client, app_state, monkeypatch):
    monkeypatch.setattr(settings, "auth_secret_key", "short-test-key")
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        with client:
            pass
    assert app_state.http.is_closed
