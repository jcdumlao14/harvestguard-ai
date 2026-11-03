"""Isolated recovery-test runner and incident lifecycle.

The recovery adapter performs one fixed HTTP request.
The verifier uses a separate HTTP client and a fresh health request.
No shell, Docker, production, or arbitrary command execution exists here.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


EXPECTED_SERVICE_ID = "harvestguard-recovery-test"


class RecoveryTestStore:
    """Separate SQLite state store for recovery-test incidents."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=5,
            isolation_level="IMMEDIATE",
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_test_incidents (
                    incident_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_test_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    FOREIGN KEY (incident_id)
                        REFERENCES recovery_test_incidents(incident_id)
                )
                """
            )

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def create_incident(
        self,
        incident_id: str,
        service_id: str = EXPECTED_SERVICE_ID,
    ) -> dict[str, Any]:
        if not incident_id or len(incident_id) > 128:
            raise ValueError("Invalid incident ID")

        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO recovery_test_incidents
                    (incident_id, status, service_id, created_at, updated_at)
                VALUES (?, 'open', ?, ?, ?)
                """,
                (incident_id, service_id, now, now),
            )
            connection.execute(
                """
                INSERT INTO recovery_test_events
                    (incident_id, event_type, actor, details, event_time)
                VALUES (?, 'incident_opened', 'recovery_test', ?, ?)
                """,
                (incident_id, "Isolated recovery-test incident opened", now),
            )

        return self.get_incident(incident_id)

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM recovery_test_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        return dict(row) if row else None

    def events(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_type, actor, details, event_time
                FROM recovery_test_events
                WHERE incident_id = ?
                ORDER BY event_id
                """,
                (incident_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _event(
        self,
        connection: sqlite3.Connection,
        incident_id: str,
        event_type: str,
        actor: str,
        details: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO recovery_test_events
                (incident_id, event_type, actor, details, event_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (incident_id, event_type, actor, details[:500], self._now()),
        )

    def start_recovery(self, incident_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM recovery_test_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Recovery-test incident not found")
            if row["status"] != "open":
                raise ValueError("Incident is not open")

            now = self._now()
            connection.execute(
                """
                UPDATE recovery_test_incidents
                SET status = 'recovery_started', updated_at = ?
                WHERE incident_id = ? AND status = 'open'
                """,
                (now, incident_id),
            )
            self._event(
                connection,
                incident_id,
                "recovery_started",
                "recovery_test_runner",
                "Fixed recovery request initiated against isolated test service",
            )

    def _record_verification(
        self,
        incident_id: str,
        evidence: dict[str, Any],
    ) -> None:
        """Persist evidence returned by the independent health verifier."""
        valid = (
            evidence.get("verified") is True
            and evidence.get("service_id") == EXPECTED_SERVICE_ID
            and evidence.get("status") == "healthy"
            and isinstance(evidence.get("recovery_generation"), int)
            and evidence.get("recovery_generation", 0) >= 1
        )

        details = json.dumps({
            "verified": valid,
            "service_id": evidence.get("service_id"),
            "status": evidence.get("status"),
            "recovery_generation": evidence.get("recovery_generation"),
        }, sort_keys=True)

        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM recovery_test_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Recovery-test incident not found")
            if row["status"] != "recovery_started":
                raise ValueError("Incident is not awaiting verification")

            self._event(
                connection,
                incident_id,
                "verification_passed" if valid else "verification_failed",
                "independent_verifier",
                details,
            )

    def resolve(self, incident_id: str) -> None:
        """Resolve only after persisted independent-verification evidence."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, service_id FROM recovery_test_incidents "
                "WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Recovery-test incident not found")
            if row["status"] != "recovery_started":
                raise ValueError("Incident is not awaiting verification")

            evidence_row = connection.execute(
                """
                SELECT event_type, details FROM recovery_test_events
                WHERE incident_id = ?
                  AND event_type IN ('verification_passed', 'verification_failed')
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (incident_id,),
            ).fetchone()

            if evidence_row is None:
                raise ValueError(
                    "Successful independent verification is required"
                )

            if evidence_row["event_type"] != "verification_passed":
                raise ValueError(
                    "Most recent independent verification did not pass"
                )

            evidence = json.loads(evidence_row["details"])
            if (
                evidence.get("verified") is not True
                or evidence.get("service_id") != EXPECTED_SERVICE_ID
                or evidence.get("service_id") != row["service_id"]
                or evidence.get("status") != "healthy"
                or not isinstance(evidence.get("recovery_generation"), int)
                or evidence.get("recovery_generation", 0) < 1
            ):
                raise ValueError(
                    "Successful independent verification is required"
                )

            now = self._now()
            connection.execute(
                """
                UPDATE recovery_test_incidents
                SET status = 'resolved', updated_at = ?
                WHERE incident_id = ? AND status = 'recovery_started'
                """,
                (now, incident_id),
            )
            self._event(
                connection,
                incident_id,
                "incident_resolved",
                "recovery_test_runner",
                "Incident resolved after persisted independent verification",
            )

    def escalate(self, incident_id: str, reason: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM recovery_test_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Recovery-test incident not found")
            if row["status"] == "resolved":
                raise ValueError("A resolved incident cannot be escalated")

            now = self._now()
            connection.execute(
                """
                UPDATE recovery_test_incidents
                SET status = 'escalated', updated_at = ?
                WHERE incident_id = ?
                """,
                (now, incident_id),
            )
            self._event(
                connection,
                incident_id,
                "incident_escalated",
                "recovery_test_runner",
                reason,
            )


class FixedRecoveryAdapter:
    """Only performs the fixed recovery-test HTTP operation."""

    def __init__(self, client: Any, token: str):
        if not token:
            raise ValueError("Recovery-test token is required")
        self.client = client
        self.token = token

    def execute(self) -> dict[str, Any]:
        response = self.client.post(
            "/internal/recover",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Recovery endpoint returned HTTP {response.status_code}"
            )
        result = response.json()
        if result.get("accepted") is not True:
            raise RuntimeError("Recovery request was not accepted")
        return result


class IndependentHealthVerifier:
    """Verifies recovery using a separate client and a fresh GET request."""

    def __init__(self, client: Any):
        self.client = client

    def verify(self) -> dict[str, Any]:
        response = self.client.get("/health")
        if response.status_code != 200:
            raise RuntimeError(
                f"Health endpoint returned HTTP {response.status_code}"
            )

        observed = response.json()
        verified = (
            observed.get("service_id") == EXPECTED_SERVICE_ID
            and observed.get("status") == "healthy"
            and isinstance(observed.get("recovery_generation"), int)
            and observed["recovery_generation"] >= 1
        )
        return {
            "verified": verified,
            "service_id": observed.get("service_id"),
            "status": observed.get("status"),
            "recovery_generation": observed.get("recovery_generation"),
        }


class RecoveryTestRunner:
    def __init__(
        self,
        *,
        recovery_client: Any,
        verifier_client: Any,
        token: str,
        store: RecoveryTestStore,
    ):
        if recovery_client is verifier_client:
            raise ValueError(
                "Recovery and verification must use separate clients"
            )

        self.adapter = FixedRecoveryAdapter(recovery_client, token)
        self.verifier = IndependentHealthVerifier(verifier_client)
        self.store = store

    def run(self, incident_id: str) -> dict[str, Any]:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise ValueError("Recovery-test incident not found")
        if incident["service_id"] != EXPECTED_SERVICE_ID:
            raise ValueError(
                "Incident is not bound to the expected isolated recovery-test service"
            )
        if incident["status"] != "open":
            raise ValueError("Only an open incident can enter recovery")

        try:
            # Confirm the service is the expected degraded test target.
            before = self.verifier.verify()
            if (
                before["service_id"] != EXPECTED_SERVICE_ID
                or before["status"] != "degraded"
            ):
                raise RuntimeError(
                    "Test service was not in the expected degraded state"
                )

            self.store.start_recovery(incident_id)
            self.adapter.execute()

            # A fresh request through the independent verifier client.
            after = self.verifier.verify()
            if after["verified"] is not True:
                raise RuntimeError(
                    "Independent health verification did not pass"
                )

            self.store._record_verification(incident_id, after)
            self.store.resolve(incident_id)
            return {
                "status": "resolved",
                "verified": True,
                "incident_id": incident_id,
                "verification": after,
            }

        except Exception as exc:
            current = self.store.get_incident(incident_id)
            if current and current["status"] != "resolved":
                self.store.escalate(
                    incident_id,
                    f"Recovery test failed closed: {type(exc).__name__}: {exc}",
                )
            return {
                "status": "escalated",
                "verified": False,
                "incident_id": incident_id,
                "error_type": type(exc).__name__,
            }
