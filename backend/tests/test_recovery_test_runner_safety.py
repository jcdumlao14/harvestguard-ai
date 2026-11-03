import pytest

from backend.app.recovery_test_harness import (
    RecoveryTestRunner,
    RecoveryTestStore,
)


def test_runner_rejects_incident_bound_to_different_service(tmp_path):
    store = RecoveryTestStore(tmp_path / "recovery-test.sqlite3")

    incident_id = "wrong-service-target"
    store.create_incident(
        incident_id,
        service_id="production-api",
    )

    runner = RecoveryTestRunner(
        recovery_client=object(),
        verifier_client=object(),
        token="isolated-test-token",
        store=store,
    )

    with pytest.raises(
        ValueError,
        match="expected isolated recovery-test service",
    ):
        runner.run(incident_id)

    incident = store.get_incident(incident_id)
    assert incident["status"] == "open"

    events = store.events(incident_id)
    assert [event["event_type"] for event in events] == [
        "incident_opened"
    ]

def test_service_rejects_short_token():
    from backend.app.recovery_test_service import create_app

    with pytest.raises(
        ValueError,
        match="at least 32 characters",
    ):
        create_app("short-test-token")