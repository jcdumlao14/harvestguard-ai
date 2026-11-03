import pytest

from app.oncall_approval import ApprovalStore


def sample_investigation():
    return {
        "investigation_status": "complete",
        "execution_authority": "read_only",
        "recovery_executed": False,
        "evidence": {"api_health": {"health_status": "unhealthy"}},
    }


def sample_assessment():
    return {
        "assessment_status": "evidence_supported",
        "severity": "critical",
        "recovery_authorized": False,
        "human_approval_required": True,
    }


def test_incident_round_trip_persists_structured_evidence(tmp_path):
    store = ApprovalStore(tmp_path / "incidents.sqlite3")

    saved = store.save_incident(
        alert_name="HarvestGuardApiUnavailable",
        fingerprint="test-fingerprint",
        investigation=sample_investigation(),
        assessment=sample_assessment(),
    )

    loaded = store.get_incident(saved["incident_id"])

    assert loaded is not None
    assert loaded["alert_name"] == "HarvestGuardApiUnavailable"
    assert loaded["fingerprint"] == "test-fingerprint"
    assert loaded["investigation"] == sample_investigation()
    assert loaded["assessment"] == sample_assessment()
    assert loaded["assessment_status"] == "evidence_supported"


def test_incident_records_receive_distinct_ids(tmp_path):
    store = ApprovalStore(tmp_path / "incidents.sqlite3")
    values = {
        "alert_name": "HarvestGuardApiUnavailable",
        "fingerprint": "same-fingerprint",
        "investigation": sample_investigation(),
        "assessment": sample_assessment(),
    }

    first = store.save_incident(**values)
    second = store.save_incident(**values)

    assert first["incident_id"] != second["incident_id"]


def test_unknown_alert_cannot_be_persisted(tmp_path):
    store = ApprovalStore(tmp_path / "incidents.sqlite3")

    with pytest.raises(ValueError, match="allowlisted"):
        store.save_incident(
            alert_name="UnknownAlert",
            fingerprint="test",
            investigation=sample_investigation(),
            assessment=sample_assessment(),
        )


def test_oversized_investigation_is_rejected(tmp_path):
    store = ApprovalStore(tmp_path / "incidents.sqlite3")

    with pytest.raises(ValueError, match="storage limit"):
        store.save_incident(
            alert_name="HarvestGuardApiUnavailable",
            fingerprint="test",
            investigation={"payload": "x" * (256 * 1024)},
            assessment=sample_assessment(),
        )


def test_missing_incident_returns_none(tmp_path):
    store = ApprovalStore(tmp_path / "incidents.sqlite3")

    assert store.get_incident("not-a-real-incident") is None
