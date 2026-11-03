from fastapi.testclient import TestClient
import pytest

from backend.app.recovery_test_service import create_app
from backend.app.recovery_test_harness import (
    RecoveryTestRunner,
    RecoveryTestStore,
)


TOKEN = "local-test-only-secret-32-bytes!!"


def make_clients():
    app = create_app(TOKEN)
    return TestClient(app), TestClient(app)


def make_runner(tmp_path, recovery_client, verifier_client):
    store = RecoveryTestStore(tmp_path / "recovery-test.sqlite3")
    runner = RecoveryTestRunner(
        recovery_client=recovery_client,
        verifier_client=verifier_client,
        token=TOKEN,
        store=store,
    )
    return store, runner


def test_service_starts_degraded_and_requires_token():
    app = create_app(TOKEN)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"

    unauthorized = client.post("/internal/recover")
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/internal/recover",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["accepted"] is True


def test_success_requires_independent_verification(tmp_path):
    recovery_client, verifier_client = make_clients()
    store, runner = make_runner(
        tmp_path, recovery_client, verifier_client
    )
    store.create_incident("recovery-success-001")

    result = runner.run("recovery-success-001")

    assert result["status"] == "resolved"
    assert result["verified"] is True

    incident = store.get_incident("recovery-success-001")
    assert incident["status"] == "resolved"

    event_types = [
        event["event_type"]
        for event in store.events("recovery-success-001")
    ]
    assert event_types == [
        "incident_opened",
        "recovery_started",
        "verification_passed",
        "incident_resolved",
    ]


def test_wrong_service_identity_escalates(tmp_path):
    recovery_client, real_verifier = make_clients()

    class WrongIdentityVerifier:
        def get(self, path):
            response = real_verifier.get(path)
            payload = response.json()
            payload["service_id"] = "unexpected-service"

            class FakeResponse:
                status_code = 200

                @staticmethod
                def json():
                    return payload

            return FakeResponse()

    store, runner = make_runner(
        tmp_path, recovery_client, WrongIdentityVerifier()
    )
    store.create_incident("recovery-wrong-identity-001")

    result = runner.run("recovery-wrong-identity-001")

    assert result["status"] == "escalated"
    assert result["verified"] is False
    assert store.get_incident("recovery-wrong-identity-001")["status"] == "escalated"


def test_failed_recovery_authorization_escalates(tmp_path):
    recovery_client, verifier_client = make_clients()
    store = RecoveryTestStore(tmp_path / "recovery-failure.sqlite3")
    store.create_incident("recovery-auth-failure-001")

    runner = RecoveryTestRunner(
        recovery_client=recovery_client,
        verifier_client=verifier_client,
        token="incorrect-token",
        store=store,
    )

    result = runner.run("recovery-auth-failure-001")

    assert result["status"] == "escalated"
    assert store.get_incident("recovery-auth-failure-001")["status"] == "escalated"


def test_incident_cannot_be_closed_without_verification(tmp_path):
    store = RecoveryTestStore(tmp_path / "recovery-closure.sqlite3")
    store.create_incident("recovery-closure-001")
    store.start_recovery("recovery-closure-001")

    with pytest.raises(
        ValueError,
        match="Successful independent verification",
    ):
        store.resolve("recovery-closure-001")

    assert store.get_incident("recovery-closure-001")["status"] == "recovery_started"


def test_recovery_and_verifier_must_be_separate_clients(tmp_path):
    client = TestClient(create_app(TOKEN))
    store = RecoveryTestStore(tmp_path / "recovery-client-separation.sqlite3")

    with pytest.raises(ValueError, match="separate clients"):
        RecoveryTestRunner(
            recovery_client=client,
            verifier_client=client,
            token=TOKEN,
            store=store,
        )


def test_resolved_incident_cannot_be_escalated(tmp_path):
    store = RecoveryTestStore(tmp_path / "recovery-terminal-state.sqlite3")
    store.create_incident("recovery-terminal-001")
    store.start_recovery("recovery-terminal-001")
    store._record_verification(
        "recovery-terminal-001",
        {
            "verified": True,
            "service_id": "harvestguard-recovery-test",
            "status": "healthy",
            "recovery_generation": 1,
        },
    )
    store.resolve("recovery-terminal-001")

    with pytest.raises(ValueError, match="cannot be escalated"):
        store.escalate("recovery-terminal-001", "Late failure")

    assert store.get_incident("recovery-terminal-001")["status"] == "resolved"

def test_failed_verification_supersedes_previous_success(tmp_path):
    store = RecoveryTestStore(
        tmp_path / "recovery-latest-verification.sqlite3"
    )
    incident_id = "recovery-latest-verification-001"

    store.create_incident(incident_id)
    store.start_recovery(incident_id)

    store._record_verification(
        incident_id,
        {
            "verified": True,
            "service_id": "harvestguard-recovery-test",
            "status": "healthy",
            "recovery_generation": 1,
        },
    )

    store._record_verification(
        incident_id,
        {
            "verified": False,
            "service_id": "harvestguard-recovery-test",
            "status": "degraded",
            "recovery_generation": 1,
        },
    )

    with pytest.raises(
        ValueError,
        match="Most recent independent verification did not pass",
    ):
        store.resolve(incident_id)

    assert store.get_incident(incident_id)["status"] == "recovery_started"
