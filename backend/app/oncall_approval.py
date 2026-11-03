"""Isolated SQLite approval and audit store for nonproduction recovery."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .oncall_contracts import ALLOWED_ALERTS


APPROVED_ACTIONS = {"simulate_health_recovery"}
APPROVED_ENVIRONMENT = "nonproduction"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class ApprovalStore:
    """Stores approval records separately from HarvestGuard business data."""

    def __init__(self, database_path: str | Path | None = None):
        if database_path is None:
            configured = os.environ.get("HARVESTGUARD_ONCALL_STATE_DB")
            if configured:
                database_path = configured
            else:
                database_path = (
                    Path.home()
                    / "AppData"
                    / "Local"
                    / "HarvestGuard"
                    / "oncall-state.sqlite3"
                )

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
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    decided_by TEXT,
                    decision_reason TEXT,
                    consumed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    details TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    alert_name TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    investigation_status TEXT NOT NULL,
                    assessment_status TEXT NOT NULL,
                    investigation_json TEXT NOT NULL,
                    assessment_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint
                ON incidents (fingerprint)
                """
            )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        approval_id: str,
        event_type: str,
        actor: str,
        details: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events
                (approval_id, event_type, actor, event_time, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (approval_id, event_type, actor, _iso(_now()), details[:500]),
        )

    @staticmethod
    def _record(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def request_approval(
        self,
        *,
        incident_id: str,
        action_name: str,
        environment: str,
        requested_by: str,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        if not incident_id or len(incident_id) > 128:
            raise ValueError("A valid incident ID is required")
        if action_name not in APPROVED_ACTIONS:
            raise ValueError("Action is not approved for the simulation executor")
        if environment != APPROVED_ENVIRONMENT:
            raise ValueError("Only the nonproduction environment is permitted")
        if not requested_by or len(requested_by) > 128:
            raise ValueError("A valid requester identity is required")
        if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 3600:
            raise ValueError("Approval expiry must be between 1 and 3600 seconds")

        approval_id = str(uuid.uuid4())
        created = _now()
        expires = created + timedelta(seconds=ttl_seconds)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals (
                    approval_id, incident_id, action_name, environment,
                    requested_by, status, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    approval_id,
                    incident_id,
                    action_name,
                    environment,
                    requested_by,
                    _iso(created),
                    _iso(expires),
                ),
            )
            self._audit(
                connection,
                approval_id,
                "approval_requested",
                requested_by,
                "Explicit human decision required",
            )
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()

        return self._record(row)

    def save_incident(
        self,
        *,
        alert_name: str,
        fingerprint: str,
        investigation: dict[str, Any],
        assessment: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist bounded structured incident evidence and its assessment."""

        if alert_name not in ALLOWED_ALERTS:
            raise ValueError("Alert is not allowlisted")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ValueError("A valid incident fingerprint is required")
        if len(fingerprint) > 256:
            raise ValueError("Incident fingerprint is too long")
        if not isinstance(investigation, dict):
            raise ValueError("Investigation must be a structured object")
        if not isinstance(assessment, dict):
            raise ValueError("Assessment must be a structured object")

        investigation_json = json.dumps(
            investigation, separators=(",", ":"), allow_nan=False
        )
        assessment_json = json.dumps(
            assessment, separators=(",", ":"), allow_nan=False
        )

        if len(investigation_json.encode("utf-8")) > 256 * 1024:
            raise ValueError("Investigation record exceeds the storage limit")
        if len(assessment_json.encode("utf-8")) > 64 * 1024:
            raise ValueError("Assessment record exceeds the storage limit")

        incident_id = str(uuid.uuid4())
        created_at = _iso(_now())
        investigation_status = str(
            investigation.get("investigation_status", "unknown")
        )[:64]
        assessment_status = str(
            assessment.get("assessment_status", "limited_evidence")
        )[:64]

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, alert_name, fingerprint,
                    investigation_status, assessment_status,
                    investigation_json, assessment_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    alert_name,
                    fingerprint,
                    investigation_status,
                    assessment_status,
                    investigation_json,
                    assessment_json,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

        return self._incident_record(row)

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        if not isinstance(incident_id, str) or not incident_id:
            return None

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

        return self._incident_record(row)

    @staticmethod
    def _incident_record(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None

        record = dict(row)
        record["investigation"] = json.loads(
            record.pop("investigation_json")
        )
        record["assessment"] = json.loads(
            record.pop("assessment_json")
        )
        return record

    def decide_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str,
        reason: str,
    ) -> dict[str, Any]:
        if not decided_by or len(decided_by) > 128:
            raise ValueError("A valid decision-maker identity is required")
        if not reason or len(reason) > 500:
            raise ValueError("A decision reason is required")

        new_status = "approved" if approved else "rejected"

        expired = False

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Approval record not found")

            if row["status"] != "pending":
                raise ValueError("Approval is no longer pending")

            if datetime.fromisoformat(row["expires_at"]) <= _now():
                connection.execute(
                    "UPDATE approvals SET status = 'expired' WHERE approval_id = ?",
                    (approval_id,),
                )
                self._audit(
                    connection,
                    approval_id,
                    "approval_expired",
                    "system",
                    "Approval expired before a decision",
                )
                expired = True
            else:
                connection.execute(
                    """
                    UPDATE approvals
                    SET status = ?, decided_by = ?, decision_reason = ?
                    WHERE approval_id = ? AND status = 'pending'
                    """,
                    (new_status, decided_by, reason, approval_id),
                )
                self._audit(
                    connection,
                    approval_id,
                    new_status,
                    decided_by,
                    reason,
                )
                updated = connection.execute(
                    "SELECT * FROM approvals WHERE approval_id = ?",
                    (approval_id,),
                ).fetchone()

        if expired:
            raise ValueError("Approval has expired")

        return self._record(updated)

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return self._record(row)

    def consume_approval(
        self,
        approval_id: str,
        *,
        incident_id: str,
        action_name: str,
        environment: str,
    ) -> dict[str, Any]:
        """Atomically consume one approved record before simulated execution."""

        if environment != APPROVED_ENVIRONMENT:
            raise ValueError("Recovery is restricted to nonproduction")

        expired = False

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Approval record not found")

            if row["status"] != "approved":
                raise ValueError("A pending, rejected, expired, or consumed approval cannot execute")

            if row["incident_id"] != incident_id:
                raise ValueError("Approval incident does not match")
            if row["action_name"] != action_name:
                raise ValueError("Approval action does not match")
            if row["environment"] != environment:
                raise ValueError("Approval environment does not match")

            if datetime.fromisoformat(row["expires_at"]) <= _now():
                connection.execute(
                    "UPDATE approvals SET status = 'expired' WHERE approval_id = ?",
                    (approval_id,),
                )
                self._audit(
                    connection,
                    approval_id,
                    "approval_expired",
                    "system",
                    "Approval expired before execution",
                )
                expired = True
            else:
                consumed = _iso(_now())
                cursor = connection.execute(
                    """
                    UPDATE approvals
                    SET status = 'consumed', consumed_at = ?
                    WHERE approval_id = ? AND status = 'approved'
                    """,
                    (consumed, approval_id),
                )

                if cursor.rowcount != 1:
                    raise ValueError("Approval could not be consumed")

                self._audit(
                    connection,
                    approval_id,
                    "approval_consumed",
                    "recovery_executor",
                    "One-time approval consumed before execution",
                )

                updated = connection.execute(
                    "SELECT * FROM approvals WHERE approval_id = ?",
                    (approval_id,),
                ).fetchone()

        if expired:
            raise ValueError("Approval has expired")

        return self._record(updated)

    def record_event(
        self,
        approval_id: str,
        event_type: str,
        *,
        actor: str,
        details: str,
    ) -> None:
        with self._connect() as connection:
            self._audit(
                connection,
                approval_id,
                event_type,
                actor,
                details,
            )

    def audit_events(self, approval_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_type, actor, event_time, details
                FROM audit_events
                WHERE approval_id = ?
                ORDER BY event_id
                """,
                (approval_id,),
            ).fetchall()

        return [dict(row) for row in rows]