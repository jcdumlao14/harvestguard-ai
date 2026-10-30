import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.oncall_webhook import router, _seen, _lock

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HARVESTGUARD_RESPONDER_TOKEN", "test-only-token")
    with _lock:
        _seen.clear()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

def auth():
    return {"Authorization": "Bearer test-only-token"}

def test_webhook_rejects_missing_auth(client):
    response = client.post(
        "/internal/alerts/alertmanager",
        json={"alerts": []},
    )
    assert response.status_code == 401

def test_webhook_rejects_unknown_alert(client):
    response = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json={"alerts": [{
            "status": "firing",
            "labels": {"alertname": "UnknownAlert"},
        }]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["decision"] == "rejected"

def test_webhook_escalates_allowlisted_alert_without_executor(client):
    response = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json={"alerts": [{
            "status": "firing",
            "fingerprint": "test-api-down",
            "labels": {"alertname": "HarvestGuardApiUnavailable"},
        }]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["decision"] == "escalate"

def test_webhook_suppresses_duplicate_alert(client):
    payload = {"alerts": [{
        "status": "firing",
        "fingerprint": "duplicate-test",
        "labels": {"alertname": "HarvestGuardApiUnavailable"},
    }]}
    first = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json=payload,
    )
    second = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json=payload,
    )
    assert first.json()["results"][0]["decision"] == "escalate"
    assert second.json()["results"][0]["decision"] == "suppressed"
