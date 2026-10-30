import hmac
import logging
import os
import time
from threading import Lock
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()
logger = logging.getLogger("harvestguard.oncall")

ALLOWED_ALERTS = {
    "HarvestGuardApiUnavailable",
    "HarvestGuardPrometheusTargetMissing",
    "HarvestGuardHighHttp5xxRate",
    "HarvestGuardHighApiLatency",
}

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

        fingerprint = str(alert.get("fingerprint", ""))
        if not fingerprint:
            fingerprint = name + ":" + str(labels.get("instance", "unknown"))

        if not _record_once(fingerprint, time.time()):
            results.append({
                "alert": name,
                "decision": "suppressed",
                "reason": "Cooldown or duplicate alert",
            })
            continue

        # Deliberately fail closed: no provider executor is installed yet.
        # This handler acknowledges and records the incident, but never
        # executes shell commands, restarts containers, or changes data.
        logger.error(
            "oncall_incident_received alert=%s fingerprint=%s decision=escalate",
            name,
            fingerprint,
        )
        results.append({
            "alert": name,
            "decision": "escalate",
            "reason": "No approved deployment recovery executor configured",
        })

    return {
        "receiver": "harvestguard-oncall",
        "processed": len(results),
        "results": results,
    }
