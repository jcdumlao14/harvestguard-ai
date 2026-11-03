import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.oncall_api import router
from app.oncall_approval import ApprovalStore


ALERT = "HarvestGuardApiUnavailable"


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HARVESTGUARD_ONCALL_STATE_DB",
        str(tmp_path / "approval-api.sqlite3"),
    )
    monkeypatch.setenv("HARVESTGUARD_ONCALL_OPERATOR_TOKEN", "operator-test-token")
    monkeypatch.setenv("HARVESTGUARD_ONCALL_OPERATOR_ID", "operator-001")
    monkeypatch.setenv("HARVESTGUARD_ONCALL_APPROVER_TOKEN", "approver-test-token")
    monkeypatch.setenv("HARVESTGUARD_ONCALL_APPROVER_ID", "approver-001")

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def eligible_incident(api_client):
    store = ApprovalStore()
    return store.save_incident(
        alert_name=ALERT,
        fingerprint="test-fingerprint",
        investigation={
            "alert": ALERT,
            "investigation_status": "complete",
            "evidence": [],
            "execution_authority": "read_only",
            "recovery_executed": False,
        },
        assessment={
            "alert": ALERT,
            "assessment_status": "evidence_supported",
            "severity": "critical",
            "confidence": "medium",
            "recovery_authorized": False,
            "human_approval_required": True,
        },
    )


def operator_auth():
    return {"Authorization": "Bearer operator-test-token"}


def approver_auth():
    return {"Authorization": "Bearer approver-test-token"}


def request_approval(client, incident_id):
    return client.post(
        f"/internal/oncall/incidents/{incident_id}/approvals",
        headers=operator_auth(),
        json={},
    )


def test_operator_authentication_fails_closed_when_unconfigured(
    api_client,
    monkeypatch,
    eligible_incident,
):
    monkeypatch.delenv("HARVESTGUARD_ONCALL_OPERATOR_TOKEN")

    response = request_approval(api_client, eligible_incident["incident_id"])

    assert response.status_code == 503


def test_operator_rejects_invalid_token(api_client, eligible_incident):
    response = api_client.post(
        f"/internal/oncall/incidents/{eligible_incident['incident_id']}/approvals",
        headers={"Authorization": "Bearer wrong-token"},
        json={},
    )

    assert response.status_code == 401


def test_requester_identity_cannot_be_supplied_by_client(
    api_client,
    eligible_incident,
):
    response = api_client.post(
        f"/internal/oncall/incidents/{eligible_incident['incident_id']}/approvals",
        headers=operator_auth(),
        json={"requested_by": "attacker"},
    )

    assert response.status_code == 422


def test_approval_request_uses_server_identity_and_fixed_policy(
    api_client,
    eligible_incident,
):
    response = request_approval(
        api_client,
        eligible_incident["incident_id"],
    )

    assert response.status_code == 201
    record = response.json()

    assert record["requested_by"] == "operator-001"
    assert record["action_name"] == "simulate_health_recovery"
    assert record["environment"] == "nonproduction"
    assert record["status"] == "pending"
    assert record["human_decision_required"] is True


def test_limited_evidence_incident_cannot_request_approval(
    api_client,
):
    store = ApprovalStore()
    incident = store.save_incident(
        alert_name=ALERT,
        fingerprint="limited-fingerprint",
        investigation={
            "alert": ALERT,
            "investigation_status": "unavailable",
            "evidence": [],
        },
        assessment={
            "alert": ALERT,
            "assessment_status": "limited_evidence",
            "recovery_authorized": False,
            "human_approval_required": True,
        },
    )

    response = request_approval(api_client, incident["incident_id"])

    assert response.status_code == 409


def test_requester_cannot_approve_own_request(
    api_client,
    eligible_incident,
    monkeypatch,
):
    monkeypatch.setenv("HARVESTGUARD_ONCALL_APPROVER_ID", "operator-001")

    requested = request_approval(api_client, eligible_incident["incident_id"])
    approval_id = requested.json()["approval_id"]

    response = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/decision",
        headers=approver_auth(),
        json={"approved": True, "reason": "Must be rejected"},
    )

    assert response.status_code == 403


def test_approval_requires_separately_authenticated_approver(
    api_client,
    eligible_incident,
    monkeypatch,
):
    requested = request_approval(api_client, eligible_incident["incident_id"])
    approval_id = requested.json()["approval_id"]

    monkeypatch.delenv("HARVESTGUARD_ONCALL_APPROVER_TOKEN")

    response = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/decision",
        headers=approver_auth(),
        json={"approved": True, "reason": "Test approval"},
    )

    assert response.status_code == 503


def test_rejected_approval_cannot_execute(
    api_client,
    eligible_incident,
):
    requested = request_approval(api_client, eligible_incident["incident_id"])
    approval_id = requested.json()["approval_id"]

    decision = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/decision",
        headers=approver_auth(),
        json={"approved": False, "reason": "Rejected for safety test"},
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"

    execution = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/execute",
        headers=operator_auth(),
    )

    assert execution.status_code == 409


def test_approved_simulation_is_one_time_and_audited(
    api_client,
    eligible_incident,
):
    requested = request_approval(api_client, eligible_incident["incident_id"])
    approval_id = requested.json()["approval_id"]

    decision = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/decision",
        headers=approver_auth(),
        json={"approved": True, "reason": "Approved for nonproduction simulation"},
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert decision.json()["decided_by"] == "approver-001"

    execution = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/execute",
        headers=operator_auth(),
    )

    assert execution.status_code == 200
    result = execution.json()

    assert result["status"] == "verified_simulation"
    assert result["verified"] is True
    assert result["recovery_executed"] is False
    assert result["external_side_effects"] is False
    assert result["result"]["simulated"] is True

    second_execution = api_client.post(
        f"/internal/oncall/approvals/{approval_id}/execute",
        headers=operator_auth(),
    )

    assert second_execution.status_code == 409

    audit = api_client.get(
        f"/internal/oncall/approvals/{approval_id}/audit",
        headers=operator_auth(),
    )

    assert audit.status_code == 200
    event_types = [event["event_type"] for event in audit.json()["events"]]

    assert "approval_requested" in event_types
    assert "approved" in event_types
    assert "approval_consumed" in event_types
    assert "recovery_started" in event_types
    assert "recovery_verified" in event_types


def test_missing_approval_returns_not_found(api_client):
    response = api_client.post(
        "/internal/oncall/approvals/missing-approval/execute",
        headers=operator_auth(),
    )

    assert response.status_code == 404