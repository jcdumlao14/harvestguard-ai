import hashlib
import hmac
import logging
import os
import time
from threading import Lock
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .oncall_approval import ApprovalStore
from .oncall_assessment import SEVERITY, assess_investigation
from .oncall_contracts import ALLOWED_ALERTS as SHARED_ALLOWED_ALERTS
from .oncall_investigation import investigate_alert

router = APIRouter()
logger = logging.getLogger("harvestguard.oncall")

# Preserve the public module-level name used by existing callers and tests.
ALLOWED_ALERTS = set(SHARED_ALLOWED_ALERTS)

# In-process deduplication is suitable for a single local instance.
# A distributed deployment must replace this with shared persistent state.
_seen: dict[str, float] = {}
_lock = Lock()
COOLDOWN_SECONDS = max(
    30, int(os.getenv("HARVESTGUARD_ALERT_COOLDOWN_SECONDS", "300"))
)


def _authorized(header: str | None) -> bool:
    expected = os.getenv("HARVESTGUARD_RESPONDER_TOKEN", "")
    if not expected:
        return False

    prefix = "Bearer "
    if not header or not header.startswith(prefix):
        return False

    return hmac.compare_digest(header[len(prefix):], expected)


def _record_once(key: str, now: float) -> bool:
    with _lock:
        expired = [
            item for item, timestamp in _seen.items()
            if now - timestamp >= COOLDOWN_SECONDS
        ]
        for item in expired:
            _seen.pop(item, None)

        previous = _seen.get(key)
        if previous is not None and now - previous < COOLDOWN_SECONDS:
            return False

        _seen[key] = now
        return True


def _forget_once(key: str) -> None:
    """Release a deduplication entry when incident persistence fails."""
    with _lock:
        _seen.pop(key, None)


def _safe_fingerprint(alert: dict[str, Any], name: str, labels: dict) -> str:
    supplied = alert.get("fingerprint")
    if supplied is None or supplied == "":
        supplied = labels.get("instance", "unknown")

    # Do not store or log an externally supplied fingerprint or instance.
    material = f"{name}:{str(supplied)}"
    return hashlib.sha256(
        material.encode("utf-8", errors="replace")
    ).hexdigest()


def _limited_investigation(name: str) -> dict[str, Any]:
    """Return a fixed, non-sensitive evidence record after collection failure."""
    sources = (
        "api_health",
        "prometheus_target_up",
        "prometheus_http_5xx_percent",
        "prometheus_http_p95_latency",
        "tempo",
    )

    return {
        "alert": name,
        "investigation_status": "unavailable",
        "collected_at": None,
        "evidence": [
            {
                "source": source,
                "status": "unavailable",
                "reason": "Investigation collection failed",
            }
            for source in sources
        ],
        "execution_authority": "read_only",
        "recovery_executed": False,
    }


def _limited_assessment(name: str) -> dict[str, Any]:
    """Fail-closed assessment used only if deterministic assessment fails."""
    return {
        "alert": name,
        "severity": SEVERITY.get(name, "warning"),
        "assessment_status": "limited_evidence",
        "symptoms": ["Evidence assessment could not be completed"],
        "evidence_summary": {},
        "likely_causes": ["Root cause is undetermined from the available evidence"],
        "confidence": "low",
        "recommendations": [
            "Continue read-only monitoring and inspect relevant service logs.",
            "Escalate to an operator; do not initiate recovery.",
        ],
        "recovery_authorized": False,
        "human_approval_required": True,
    }


async def _process_firing_alert(
    name: str,
    fingerprint: str,
) -> dict[str, Any]:
    """Investigate, assess, and persist one allowlisted firing alert."""

    try:
        investigation = await run_in_threadpool(
            investigate_alert,
            name,
        )
        if not isinstance(investigation, dict):
            raise ValueError("Investigation returned an invalid record")
    except Exception as exc:
        logger.warning(
            "oncall_investigation_failed alert=%s failure_type=%s",
            name,
            type(exc).__name__,
        )
        investigation = _limited_investigation(name)

    try:
        assessment = await run_in_threadpool(
            assess_investigation,
            investigation,
        )
        if not isinstance(assessment, dict):
            raise ValueError("Assessment returned an invalid record")
    except Exception as exc:
        logger.warning(
            "oncall_assessment_failed alert=%s failure_type=%s",
            name,
            type(exc).__name__,
        )
        assessment = _limited_assessment(name)

    try:
        store = await run_in_threadpool(ApprovalStore)
        incident = await run_in_threadpool(
            store.save_incident,
            alert_name=name,
            fingerprint=fingerprint,
            investigation=investigation,
            assessment=assessment,
        )
    except Exception as exc:
        _forget_once(fingerprint)
        logger.error(
            "oncall_incident_persistence_failed alert=%s failure_type=%s",
            name,
            type(exc).__name__,
        )
        return {
            "alert": name,
            "decision": "escalate",
            "reason": "Incident persistence failed; operator escalation required",
            "incident_persisted": False,
            "recovery_authorized": False,
            "recovery_executed": False,
        }

    logger.error(
        "oncall_incident_received alert=%s incident_id=%s decision=escalate",
        name,
        incident["incident_id"],
    )

    return {
        "alert": name,
        "decision": "escalate",
        "reason": "Incident investigated and recorded; explicit human approval remains required",
        "incident_id": incident["incident_id"],
        "incident_persisted": True,
        "investigation_status": incident["investigation_status"],
        "assessment_status": incident["assessment_status"],
        "severity": assessment.get("severity", "unknown"),
        "confidence": assessment.get("confidence", "low"),
        "recovery_authorized": False,
        "recovery_executed": False,
    }


@router.post("/internal/alerts/alertmanager")
async def receive_alertmanager_alert(
    request: Request,
    authorization: str | None = Header(default=None),
):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    alerts = payload.get("alerts", [])
    if not isinstance(alerts, list):
        raise HTTPException(status_code=400, detail="Invalid alerts collection")

    results = []

    for alert in alerts[:50]:
        if not isinstance(alert, dict):
            continue

        labels = alert.get("labels") or {}
        if not isinstance(labels, dict):
            labels = {}

        name = str(labels.get("alertname", ""))
        status = str(alert.get("status", payload.get("status", "firing")))

        if name not in ALLOWED_ALERTS:
            results.append({
                "alert": name or "unknown",
                "decision": "rejected",
                "reason": "Alert is not allowlisted",
            })
            continue

        if status.lower() != "firing":
            results.append({
                "alert": name,
                "decision": "observed",
                "reason": "Alert is not firing",
            })
            continue

        fingerprint = _safe_fingerprint(alert, name, labels)

        if not _record_once(fingerprint, time.time()):
            results.append({
                "alert": name,
                "decision": "suppressed",
                "reason": "Cooldown or duplicate alert",
            })
            continue

        result = await _process_firing_alert(name, fingerprint)
        results.append(result)

    return {
        "receiver": "harvestguard-oncall",
        "processed": len(results),
        "results": results,
    }