"""Explicitly approved, nonproduction recovery simulation only."""

from __future__ import annotations

from typing import Any, Protocol

from .oncall_approval import (
    APPROVED_ACTIONS,
    APPROVED_ENVIRONMENT,
    ApprovalStore,
)


class RecoveryAdapter(Protocol):
    def execute(self, action_name: str) -> dict[str, Any]:
        ...

    def verify(self, action_name: str, result: dict[str, Any]) -> bool:
        ...


class SimulatedRecoveryAdapter:
    """A deterministic simulation. It does not contact or change any service."""

    def execute(self, action_name: str) -> dict[str, Any]:
        if action_name not in APPROVED_ACTIONS:
            raise ValueError("Action is not allowlisted")

        return {
            "simulated": True,
            "action": action_name,
            "before": "degraded",
            "after": "healthy",
            "external_side_effects": False,
        }

    def verify(self, action_name: str, result: dict[str, Any]) -> bool:
        return bool(
            action_name in APPROVED_ACTIONS
            and result.get("simulated") is True
            and result.get("after") == "healthy"
            and result.get("external_side_effects") is False
        )


def execute_recovery(
    store: ApprovalStore,
    *,
    approval_id: str,
    incident_id: str,
    action_name: str,
    environment: str,
    adapter: RecoveryAdapter | None = None,
) -> dict[str, Any]:
    """Consume explicit approval, simulate one action, independently verify."""

    if action_name not in APPROVED_ACTIONS:
        raise ValueError("Recovery action is not allowlisted")

    if environment != APPROVED_ENVIRONMENT:
        raise ValueError("Only nonproduction recovery simulation is permitted")

    # Consumption is atomic and occurs before any adapter invocation.
    consumed = store.consume_approval(
        approval_id,
        incident_id=incident_id,
        action_name=action_name,
        environment=environment,
    )

    store.record_event(
        approval_id,
        "recovery_started",
        actor="recovery_executor",
        details="Nonproduction simulation started",
    )

    selected_adapter = adapter or SimulatedRecoveryAdapter()

    try:
        result = selected_adapter.execute(action_name)

        verified = selected_adapter.verify(action_name, result)

        if not verified:
            store.record_event(
                approval_id,
                "recovery_verification_failed",
                actor="recovery_verifier",
                details="Independent verification did not pass; fail closed",
            )
            return {
                "status": "verification_failed",
                "verified": False,
                "recovery_executed": False,
                "approval_status": consumed["status"],
                "result": result,
                "disposition": "escalate",
            }

        store.record_event(
            approval_id,
            "recovery_verified",
            actor="recovery_verifier",
            details="Simulation result independently verified",
        )

        return {
            "status": "verified_simulation",
            "verified": True,
            "recovery_executed": False,
            "approval_status": consumed["status"],
            "result": result,
            "disposition": "simulation_complete",
        }

    except Exception as exc:
        store.record_event(
            approval_id,
            "recovery_execution_failed",
            actor="recovery_executor",
            details=f"Failure type: {type(exc).__name__}; fail closed",
        )
        return {
            "status": "execution_failed",
            "verified": False,
            "recovery_executed": False,
            "approval_status": consumed["status"],
            "result": None,
            "disposition": "escalate",
        }