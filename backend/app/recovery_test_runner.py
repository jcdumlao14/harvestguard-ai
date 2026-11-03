"""One-shot HTTP runner for the isolated recovery-test environment."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import httpx

from app.recovery_test_harness import (
    EXPECTED_SERVICE_ID,
    RecoveryTestRunner,
    RecoveryTestStore,
)


def main() -> int:
    token = os.environ.get("HARVESTGUARD_RECOVERY_TEST_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError(
            "A dedicated recovery-test token of at least 32 characters is required"
        )

    service_url = os.environ.get(
        "HARVESTGUARD_RECOVERY_TEST_URL",
        "http://recovery-test-service:8000",
    ).rstrip("/")

    database_path = Path(
        os.environ.get(
            "HARVESTGUARD_RECOVERY_TEST_DB",
            "/tmp/recovery-test.sqlite3",
        )
    )

    store = RecoveryTestStore(database_path)
    incident_id = f"stage6-{uuid.uuid4().hex}"

    # These are intentionally distinct HTTP client instances.
    with (
        httpx.Client(
            base_url=service_url,
            timeout=httpx.Timeout(5.0),
            trust_env=False,
        ) as recovery_client,
        httpx.Client(
            base_url=service_url,
            timeout=httpx.Timeout(5.0),
            trust_env=False,
        ) as verifier_client,
    ):
        store.create_incident(
            incident_id,
            service_id=EXPECTED_SERVICE_ID,
        )

        runner = RecoveryTestRunner(
            recovery_client=recovery_client,
            verifier_client=verifier_client,
            token=token,
            store=store,
        )

        result = runner.run(incident_id)

    report = {
        "incident": store.get_incident(incident_id),
        "result": result,
        "audit_events": store.events(incident_id),
    }

    print("=== ISOLATED RECOVERY TEST REPORT ===")
    print(json.dumps(report, indent=2, default=str))

    if result.get("status") == "resolved" and result.get("verified") is True:
        print("STAGE 6 RESULT: PASS")
        return 0

    print("STAGE 6 RESULT: FAIL - INCIDENT ESCALATED")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"STAGE 6 RUNNER ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)