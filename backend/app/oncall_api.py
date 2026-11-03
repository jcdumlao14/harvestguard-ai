"""Authenticated operator and approver API for on-call simulations."""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .oncall_approval import (
    APPROVED_ACTIONS,
    APPROVED_ENVIRONMENT,
    ApprovalStore,
)
from .oncall_recovery import execute_recovery

router = APIRouter(prefix="/internal/oncall", tags=["on-call-approval"])

SIMULATION_ACTION = "simulate_health_recovery"


class ApprovalRequest(BaseModel):
    """An intentionally empty request: identity and action are server-defined."""

    model_config = ConfigDict(extra="forbid")


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str = Field(min_length=1, max_length=500)


def _authenticate(
    authorization: str | None,
    *,
    token_variable: str,
    identity_variable: str,
) -> str:
    expected_token = os.getenv(token_variable, "")
    actor = os.getenv(identity_variable, "")

    if not expected_token or not actor or len(actor) > 128:
        raise HTTPException(
            status_code=503,
            detail="On-call authentication is not configured",
        )

    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Unauthorized")

    supplied = authorization[len(prefix):]
    if not hmac.compare_digest(supplied, expected_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return actor


def _operator(authorization: str | None) -> str:
    return _authenticate(
        authorization,
        token_variable="HARVESTGUARD_ONCALL_OPERATOR_TOKEN",
        identity_variable="HARVESTGUARD_ONCALL_OPERATOR_ID",
    )


def _approver(authorization: str | None) -> str:
    return _authenticate(
        authorization,
        token_variable="HARVESTGUARD_ONCALL_APPROVER_TOKEN",
        identity_variable="HARVESTGUARD_ONCALL_APPROVER_ID",
    )


async def _store() -> ApprovalStore:
    try:
        return await run_in_threadpool(ApprovalStore)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="On-call state store is unavailable",
        ) from exc


def _require_eligible_incident(incident: dict[str, Any] | None) -> None:
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    assessment = incident.get("assessment")
    if not isinstance(assessment, dict):
        raise HTTPException(
            status_code=409,
            detail="Incident assessment is unavailable",
        )

    eligible = (
        incident.get("investigation_status") == "complete"
        and incident.get("assessment_status") == "evidence_supported"
        and assessment.get("assessment_status") == "evidence_supported"
        and assessment.get("recovery_authorized") is False
        and assessment.get("human_approval_required") is True
    )

    if not eligible:
        raise HTTPException(
            status_code=409,
            detail="Incident does not meet the evidence requirements for approval",
        )


@router.post("/incidents/{incident_id}/approvals", status_code=201)
async def request_incident_approval(
    incident_id: str,
    payload: ApprovalRequest,
    authorization: str | None = Header(default=None),
):
    """Request a fixed nonproduction simulation approval."""

    requester = _operator(authorization)
    store = await _store()

    incident = await run_in_threadpool(store.get_incident, incident_id)
    _require_eligible_incident(incident)

    try:
        approval = await run_in_threadpool(
            store.request_approval,
            incident_id=incident_id,
            action_name=SIMULATION_ACTION,
            environment=APPROVED_ENVIRONMENT,
            requested_by=requester,
            ttl_seconds=900,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Approval request could not be persisted",
        ) from exc

    return {
        "approval_id": approval["approval_id"],
        "incident_id": approval["incident_id"],
        "action_name": approval["action_name"],
        "environment": approval["environment"],
        "requested_by": approval["requested_by"],
        "status": approval["status"],
        "expires_at": approval["expires_at"],
        "human_decision_required": True,
    }


@router.post("/approvals/{approval_id}/decision")
async def decide_incident_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    authorization: str | None = Header(default=None),
):
    """Record an explicit decision from a separately configured approver."""

    approver = _approver(authorization)

    if not payload.reason.strip():
        raise HTTPException(
            status_code=422,
            detail="A non-empty decision reason is required",
        )

    store = await _store()
    record = await run_in_threadpool(store.get_approval, approval_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approver == record["requested_by"]:
        raise HTTPException(
            status_code=403,
            detail="The requester cannot approve their own request",
        )

    try:
        updated = await run_in_threadpool(
            store.decide_approval,
            approval_id,
            approved=payload.approved,
            decided_by=approver,
            reason=payload.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Approval decision could not be persisted",
        ) from exc

    return {
        "approval_id": updated["approval_id"],
        "incident_id": updated["incident_id"],
        "status": updated["status"],
        "requested_by": updated["requested_by"],
        "decided_by": updated["decided_by"],
        "decision_reason": updated["decision_reason"],
        "expires_at": updated["expires_at"],
    }


@router.post("/approvals/{approval_id}/execute")
async def execute_approved_simulation(
    approval_id: str,
    authorization: str | None = Header(default=None),
):
    """Execute only the fixed, approved, nonproduction simulation."""

    _operator(authorization)
    store = await _store()

    record = await run_in_threadpool(store.get_approval, approval_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    if record["status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only an approved, unexpired request can be executed",
        )

    if record["requested_by"] == record["decided_by"]:
        raise HTTPException(
            status_code=403,
            detail="Requester and approver must be different identities",
        )

    if (
        record["action_name"] not in APPROVED_ACTIONS
        or record["action_name"] != SIMULATION_ACTION
        or record["environment"] != APPROVED_ENVIRONMENT
    ):
        raise HTTPException(
            status_code=409,
            detail="Approval does not match the fixed simulation policy",
        )

    incident = await run_in_threadpool(
        store.get_incident,
        record["incident_id"],
    )
    _require_eligible_incident(incident)

    try:
        result = await run_in_threadpool(
            execute_recovery,
            store,
            approval_id=approval_id,
            incident_id=record["incident_id"],
            action_name=SIMULATION_ACTION,
            environment=APPROVED_ENVIRONMENT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Simulation could not be completed; escalate for review",
        ) from exc

    return {
        "approval_id": approval_id,
        "incident_id": record["incident_id"],
        "status": result["status"],
        "verified": result["verified"],
        "recovery_executed": False,
        "external_side_effects": False,
        "disposition": result["disposition"],
        "result": result["result"],
    }


@router.get("/approvals/{approval_id}/audit")
async def get_approval_audit(
    approval_id: str,
    authorization: str | None = Header(default=None),
):
    """Read the audit trail for one approval."""

    _operator(authorization)
    store = await _store()

    record = await run_in_threadpool(store.get_approval, approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    events = await run_in_threadpool(store.audit_events, approval_id)

    return {
        "approval_id": approval_id,
        "status": record["status"],
        "events": events,
    }