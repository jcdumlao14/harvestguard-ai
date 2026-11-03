from __future__ import annotations

import pytest

from app.oncall_assessment import assess_investigation
from app.oncall_approval import ApprovalStore
from app.oncall_recovery import execute_recovery


ALERT = "HarvestGuardHighHttp5xxRate"


def make_investigation(
    *,
    health="ok",
    target=1,
    errors=7.5,
    latency=1.4,
):
    return {
        "alert": ALERT,
        "status": "complete",
        "evidence": {
            "api_health": {
                "source": "api_health",
                "status": "available",
                "health_status": health,
            },
            "prometheus_target_up": {
                "source": "prometheus_target_up",
                "status": "available",
                "samples": [{"value": target}],
            },
            "prometheus_http_5xx_percent": {
                "source": "prometheus_http_5xx_percent",
                "status": "available",
                "samples": [{"value": errors}],
            },
            "prometheus_http_p95_latency": {
                "source": "prometheus_http_p95_latency",
                "status": "available",
                "samples": [{"value": latency}],
            },
        },
    }


# ---------------- STAGE 3 ----------------

def test_assessment_reports_high_5xx_and_latency():
    result = assess_investigation(make_investigation())

    assert result["severity"] == "warning"
    assert result["assessment_status"] == "evidence_supported"
    assert any("5xx" in item for item in result["symptoms"])
    assert any("latency" in item.lower() for item in result["symptoms"])
    assert result["recovery_authorized"] is False
    assert result["human_approval_required"] is True


def test_assessment_does_not_invent_root_cause_from_healthy_evidence():
    result = assess_investigation(
        make_investigation(target=1, errors=0.5, latency=0.2)
    )

    assert result["likely_causes"] == [
        "Root cause is undetermined from the available evidence"
    ]
    assert result["recovery_authorized"] is False


def test_assessment_includes_stage2_tempo_evidence():
    investigation = make_investigation()
    investigation["evidence"]["tempo"] = {
        "source": "tempo",
        "status": "available",
        "trace_count": 1,
        "trace_ids": ["0123456789abcdef0123456789abcdef"],
    }

    result = assess_investigation(investigation)

    assert result["evidence_summary"]["tempo_traces"] == "available"


def test_assessment_reports_target_down():
    result = assess_investigation(make_investigation(target=0))

    assert any("target as down" in item for item in result["symptoms"])


def test_assessment_handles_unavailable_sources():
    investigation = {
        "alert": ALERT,
        "evidence": {
            "api_health": {
                "source": "api_health",
                "status": "unavailable",
                "reason": "ConnectError",
            }
        },
    }

    result = assess_investigation(investigation)

    assert result["assessment_status"] == "limited_evidence"
    assert result["confidence"] == "low"
    assert result["recovery_authorized"] is False


def test_assessment_rejects_unknown_alert():
    with pytest.raises(ValueError):
        assess_investigation({
            "alert": "UnknownAlert",
            "evidence": {},
        })


def test_assessment_rejects_unstructured_evidence():
    with pytest.raises(ValueError):
        assess_investigation({
            "alert": ALERT,
            "evidence": "run this command",
        })


# ---------------- STAGE 4 ----------------

def test_approval_requires_explicit_human_decision(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")

    record = store.request_approval(
        incident_id="incident-001",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
    )

    assert record["status"] == "pending"
    assert record["decided_by"] is None

    approved = store.decide_approval(
        record["approval_id"],
        approved=True,
        decided_by="operator-b",
        reason="Approved for isolated simulation",
    )

    assert approved["status"] == "approved"
    assert approved["decided_by"] == "operator-b"


def test_approval_rejection_is_recorded(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")

    record = store.request_approval(
        incident_id="incident-002",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
    )

    rejected = store.decide_approval(
        record["approval_id"],
        approved=False,
        decided_by="operator-b",
        reason="Evidence is incomplete",
    )

    assert rejected["status"] == "rejected"

    with pytest.raises(ValueError):
        store.consume_approval(
            record["approval_id"],
            incident_id="incident-002",
            action_name="simulate_health_recovery",
            environment="nonproduction",
        )


def test_unknown_action_and_production_are_rejected(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")

    with pytest.raises(ValueError):
        store.request_approval(
            incident_id="incident-003",
            action_name="restart_demo_api",
            environment="nonproduction",
            requested_by="operator-a",
        )

    with pytest.raises(ValueError):
        store.request_approval(
            incident_id="incident-003",
            action_name="simulate_health_recovery",
            environment="production",
            requested_by="operator-a",
        )


def test_expired_approval_cannot_be_approved(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")

    record = store.request_approval(
        incident_id="incident-004",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
        ttl_seconds=1,
    )

    import time
    time.sleep(1.1)

    with pytest.raises(ValueError, match="expired"):
        store.decide_approval(
            record["approval_id"],
            approved=True,
            decided_by="operator-b",
            reason="Too late",
        )


# ---------------- STAGE 5 ----------------

def approved_record(store, incident_id="incident-005"):
    record = store.request_approval(
        incident_id=incident_id,
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
    )

    store.decide_approval(
        record["approval_id"],
        approved=True,
        decided_by="operator-b",
        reason="Approved isolated simulation",
    )

    return record


def test_recovery_requires_approval(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")

    record = store.request_approval(
        incident_id="incident-006",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
    )

    with pytest.raises(ValueError):
        execute_recovery(
            store,
            approval_id=record["approval_id"],
            incident_id="incident-006",
            action_name="simulate_health_recovery",
            environment="nonproduction",
        )


def test_approved_recovery_is_simulated_and_verified(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")
    record = approved_record(store)

    result = execute_recovery(
        store,
        approval_id=record["approval_id"],
        incident_id="incident-005",
        action_name="simulate_health_recovery",
        environment="nonproduction",
    )

    assert result["status"] == "verified_simulation"
    assert result["verified"] is True
    assert result["recovery_executed"] is False
    assert result["result"]["external_side_effects"] is False

    events = store.audit_events(record["approval_id"])
    event_types = [event["event_type"] for event in events]

    assert "approval_requested" in event_types
    assert "approved" in event_types
    assert "approval_consumed" in event_types
    assert "recovery_started" in event_types
    assert "recovery_verified" in event_types


def test_approval_cannot_be_reused(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")
    record = approved_record(store)

    execute_recovery(
        store,
        approval_id=record["approval_id"],
        incident_id="incident-005",
        action_name="simulate_health_recovery",
        environment="nonproduction",
    )

    with pytest.raises(ValueError):
        execute_recovery(
            store,
            approval_id=record["approval_id"],
            incident_id="incident-005",
            action_name="simulate_health_recovery",
            environment="nonproduction",
        )


def test_recovery_rejects_wrong_incident_and_production(tmp_path):
    store = ApprovalStore(tmp_path / "approval.sqlite3")
    record = approved_record(store)

    with pytest.raises(ValueError):
        execute_recovery(
            store,
            approval_id=record["approval_id"],
            incident_id="different-incident",
            action_name="simulate_health_recovery",
            environment="nonproduction",
        )

    with pytest.raises(ValueError):
        execute_recovery(
            store,
            approval_id=record["approval_id"],
            incident_id="incident-005",
            action_name="simulate_health_recovery",
            environment="production",
        )


def test_verification_failure_fails_closed(tmp_path):
    class FailingVerifier:
        def execute(self, action_name):
            return {
                "simulated": True,
                "action": action_name,
                "after": "unknown",
                "external_side_effects": False,
            }

        def verify(self, action_name, result):
            return False

    store = ApprovalStore(tmp_path / "approval.sqlite3")
    record = approved_record(store)

    result = execute_recovery(
        store,
        approval_id=record["approval_id"],
        incident_id="incident-005",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        adapter=FailingVerifier(),
    )

    assert result["status"] == "verification_failed"
    assert result["verified"] is False
    assert result["disposition"] == "escalate"
    assert result["recovery_executed"] is False

def test_expired_decision_persists_status_and_audit(tmp_path):
    store = ApprovalStore(tmp_path / "expired-decision.sqlite3")

    record = store.request_approval(
        incident_id="incident-expired-decision",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
        ttl_seconds=1,
    )

    import time
    time.sleep(1.1)

    with pytest.raises(ValueError, match="expired"):
        store.decide_approval(
            record["approval_id"],
            approved=True,
            decided_by="operator-b",
            reason="Too late",
        )

    saved = store.get_approval(record["approval_id"])
    assert saved["status"] == "expired"

    events = store.audit_events(record["approval_id"])
    assert "approval_expired" in [event["event_type"] for event in events]


def test_expired_approved_record_persists_before_consumption_error(tmp_path):
    store = ApprovalStore(tmp_path / "expired-consumption.sqlite3")

    record = store.request_approval(
        incident_id="incident-expired-consumption",
        action_name="simulate_health_recovery",
        environment="nonproduction",
        requested_by="operator-a",
        ttl_seconds=1,
    )

    store.decide_approval(
        record["approval_id"],
        approved=True,
        decided_by="operator-b",
        reason="Approved for isolated simulation",
    )

    import time
    time.sleep(1.1)

    with pytest.raises(ValueError, match="expired"):
        store.consume_approval(
            record["approval_id"],
            incident_id="incident-expired-consumption",
            action_name="simulate_health_recovery",
            environment="nonproduction",
        )

    saved = store.get_approval(record["approval_id"])
    assert saved["status"] == "expired"

    events = store.audit_events(record["approval_id"])
    assert "approval_expired" in [event["event_type"] for event in events]
