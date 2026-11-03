import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.oncall_webhook as oncall_webhook
from app.oncall_approval import ApprovalStore


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("HARVESTGUARD_RESPONDER_TOKEN", "test-only-token")
    monkeypatch.setenv(
        "HARVESTGUARD_ONCALL_STATE_DB",
        str(tmp_path / "oncall-test.sqlite3"),
    )

    with oncall_webhook._lock:
        oncall_webhook._seen.clear()

    app = FastAPI()
    app.include_router(oncall_webhook.router)
    return TestClient(app)


def auth():
    return {"Authorization": "Bearer test-only-token"}


def fake_investigation(alert_name):
    return {
        "alert": alert_name,
        "investigation_status": "complete",
        "collected_at": "2026-11-03T00:00:00+00:00",
        "evidence": [
            {
                "source": "api_health",
                "status": "available",
                "health_status": "ok",
            },
            {
                "source": "prometheus_target_up",
                "status": "available",
                "value": 1,
            },
        ],
        "execution_authority": "read_only",
        "recovery_executed": False,
    }


def fake_assessment(alert_name):
    return {
        "alert": alert_name,
        "severity": "critical",
        "assessment_status": "evidence_supported",
        "symptoms": ["Test evidence collected"],
        "evidence_summary": {},
        "likely_causes": ["Test cause"],
        "confidence": "medium",
        "recommendations": ["Continue read-only monitoring"],
        "recovery_authorized": False,
        "human_approval_required": True,
    }


@pytest.fixture
def mocked_processing(monkeypatch):
    monkeypatch.setattr(
        oncall_webhook,
        "investigate_alert",
        fake_investigation,
    )
    monkeypatch.setattr(
        oncall_webhook,
        "assess_investigation",
        lambda investigation: fake_assessment(investigation["alert"]),
    )


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


def test_webhook_investigates_assesses_and_persists_incident(
    client,
    mocked_processing,
):
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
    result = response.json()["results"][0]

    assert result["decision"] == "escalate"
    assert result["incident_persisted"] is True
    assert result["investigation_status"] == "complete"
    assert result["assessment_status"] == "evidence_supported"
    assert result["recovery_authorized"] is False
    assert result["recovery_executed"] is False
    assert result["incident_id"]

    store = ApprovalStore()
    incident = store.get_incident(result["incident_id"])

    assert incident is not None
    assert incident["alert_name"] == "HarvestGuardApiUnavailable"
    assert incident["assessment"]["human_approval_required"] is True


def test_webhook_suppresses_duplicate_alert(client, mocked_processing):
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


def test_investigation_failure_persists_limited_evidence(
    client,
    monkeypatch,
):
    def fail_investigation(alert_name):
        raise TimeoutError("test-only failure")

    monkeypatch.setattr(
        oncall_webhook,
        "investigate_alert",
        fail_investigation,
    )

    response = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json={"alerts": [{
            "status": "firing",
            "fingerprint": "investigation-failure",
            "labels": {"alertname": "HarvestGuardApiUnavailable"},
        }]},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]

    assert result["decision"] == "escalate"
    assert result["incident_persisted"] is True
    assert result["investigation_status"] == "unavailable"
    assert result["assessment_status"] == "limited_evidence"
    assert result["recovery_authorized"] is False
    assert result["recovery_executed"] is False


def test_persistence_failure_releases_deduplication_entry(
    client,
    mocked_processing,
    monkeypatch,
):
    class FailingStore:
        def save_incident(self, **kwargs):
            raise OSError("test-only persistence failure")

    monkeypatch.setattr(
        oncall_webhook,
        "ApprovalStore",
        FailingStore,
    )

    response = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json={"alerts": [{
            "status": "firing",
            "fingerprint": "persistence-failure",
            "labels": {"alertname": "HarvestGuardApiUnavailable"},
        }]},
    )

    result = response.json()["results"][0]
    assert result["decision"] == "escalate"
    assert result["incident_persisted"] is False
    assert result["recovery_authorized"] is False
    assert result["recovery_executed"] is False

    fingerprint = oncall_webhook._safe_fingerprint(
        {
            "fingerprint": "persistence-failure",
        },
        "HarvestGuardApiUnavailable",
        {},
    )
    with oncall_webhook._lock:
        assert fingerprint not in oncall_webhook._seen


def test_non_firing_allowlisted_alert_is_only_observed(client):
    response = client.post(
        "/internal/alerts/alertmanager",
        headers=auth(),
        json={"alerts": [{
            "status": "resolved",
            "fingerprint": "resolved-test",
            "labels": {"alertname": "HarvestGuardApiUnavailable"},
        }]},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["decision"] == "observed"