"""Deterministic, evidence-grounded incident assessment."""

from __future__ import annotations

from typing import Any

from .oncall_contracts import ALLOWED_ALERTS


SEVERITY = {
    "HarvestGuardApiUnavailable": "critical",
    "HarvestGuardPrometheusTargetMissing": "critical",
    "HarvestGuardHighHttp5xxRate": "warning",
    "HarvestGuardHighApiLatency": "warning",
}


def _find_source(node: Any, source_name: str) -> dict[str, Any] | None:
    """Find a named evidence source without accepting executable input."""

    if isinstance(node, dict):
        if node.get("source") == source_name:
            return node

        candidate = node.get(source_name)
        if isinstance(candidate, dict):
            return candidate

        for value in node.values():
            found = _find_source(value, source_name)
            if found is not None:
                return found

    elif isinstance(node, list):
        for value in node:
            found = _find_source(value, source_name)
            if found is not None:
                return found

    return None


def _numeric_values(node: Any) -> list[float]:
    """Extract bounded numeric values from a structured metric result."""

    output: list[float] = []

    if isinstance(node, bool):
        return output

    if isinstance(node, (int, float)):
        output.append(float(node))
        return output

    if isinstance(node, str):
        try:
            output.append(float(node))
        except ValueError:
            pass
        return output

    if isinstance(node, dict):
        # Prefer explicit metric-value fields over timestamps or labels.
        for key in ("value", "values", "samples", "sample"):
            if key in node:
                output.extend(_numeric_values(node[key]))
        return output

    if isinstance(node, (list, tuple)):
        for item in node:
            output.extend(_numeric_values(item))
        return output

    return output


def _available(source: dict[str, Any] | None) -> bool:
    return bool(source and source.get("status") == "available")


def assess_investigation(
    investigation: dict[str, Any],
) -> dict[str, Any]:
    """Assess an investigation result. This function never authorizes recovery."""

    if not isinstance(investigation, dict):
        raise ValueError("Investigation must be a structured object")

    alert = investigation.get("alert") or investigation.get("alert_name")

    if alert not in ALLOWED_ALERTS or alert not in SEVERITY:
        raise ValueError("Alert is not allowlisted for assessment")

    evidence = investigation.get("evidence")
    if not isinstance(evidence, (dict, list)):
        raise ValueError("Investigation evidence must be a structured object")

    symptoms: list[str] = []
    causes: list[str] = []
    recommendations: list[str] = []
    summaries: dict[str, Any] = {}

    health = _find_source(evidence, "api_health")
    target = _find_source(evidence, "prometheus_target_up")
    if target is None:
        target = _find_source(evidence, "prometheus_target_up_metric")

    errors = _find_source(evidence, "prometheus_http_5xx_percent")
    latency = _find_source(evidence, "prometheus_http_p95_latency")
    tempo = _find_source(evidence, "tempo")
    if tempo is None:
        tempo = _find_source(evidence, "tempo_traces")

    if health is not None:
        summaries["api_health"] = health.get("status", "unknown")

        health_status = health.get("health_status")
        if _available(health) and isinstance(health_status, str):
            if health_status.lower() != "ok":
                symptoms.append("API health endpoint reports a non-OK status")
                causes.append("API application health is degraded")
            else:
                summaries["api_health_result"] = "ok"
        elif not _available(health):
            summaries["api_health_result"] = "unavailable"

    if target is not None:
        summaries["prometheus_target"] = target.get("status", "unknown")

        if _available(target):
            values = _numeric_values(target)
            if values:
                if values[-1] == 0:
                    symptoms.append("Prometheus reports the API target as down")
                    causes.append("The monitored API target may be unreachable")
                elif values[-1] == 1:
                    summaries["prometheus_target_result"] = "up"
                else:
                    summaries["prometheus_target_result"] = "unknown"
            else:
                summaries["prometheus_target_result"] = "missing_metric_value"

    if errors is not None:
        summaries["http_5xx_percent"] = errors.get("status", "unknown")

        if _available(errors):
            values = _numeric_values(errors)
            if values:
                value = values[-1]
                summaries["http_5xx_percent_value"] = value

                if value > 5:
                    symptoms.append("Observed HTTP 5xx percentage exceeds 5%")
                    causes.append("Elevated server-side HTTP error rate")
            else:
                summaries["http_5xx_percent_value"] = None

    if latency is not None:
        summaries["http_p95_latency"] = latency.get("status", "unknown")

        if _available(latency):
            values = _numeric_values(latency)
            if values:
                value = values[-1]
                summaries["http_p95_latency_seconds"] = value

                if value > 1:
                    symptoms.append("Observed p95 API latency exceeds one second")
                    causes.append("Elevated API response latency")

    if tempo is not None:
        summaries["tempo_traces"] = tempo.get("status", "unknown")
        # Trace presence is supporting evidence, not proof of a root cause.

    if not symptoms:
        symptoms.append("No independent degradation was confirmed by the supplied evidence")

    if not causes:
        causes.append("Root cause is undetermined from the available evidence")

    recommendations.append(
        "Continue read-only monitoring and inspect the relevant service logs."
    )
    recommendations.append(
        "Escalate to an operator if the alert persists or evidence remains incomplete."
    )

    # Only independently available and valid evidence counts.
    # Unavailable sources and summary metadata do not increase confidence.
    observed_sources = 0

    health = _find_source(evidence, "api_health")
    if (
        _available(health)
        and isinstance(health.get("health_status"), str)
    ):
        observed_sources += 1

    target = _find_source(evidence, "prometheus_target_up")
    if target is None:
        target = _find_source(evidence, "prometheus_target_up_metric")
    if _available(target) and _numeric_values(target):
        observed_sources += 1

    errors = _find_source(evidence, "prometheus_http_5xx_percent")
    if _available(errors) and _numeric_values(errors):
        observed_sources += 1

    latency = _find_source(evidence, "prometheus_http_p95_latency")
    if _available(latency) and _numeric_values(latency):
        observed_sources += 1

    corroborated = observed_sources >= 2
    confidence = "medium" if corroborated and len(causes) > 1 else "low"

    return {
        "alert": alert,
        "severity": SEVERITY[alert],
        "assessment_status": (
            "evidence_supported" if corroborated else "limited_evidence"
        ),
        "symptoms": symptoms,
        "evidence_summary": summaries,
        "likely_causes": causes,
        "confidence": confidence,
        "recommendations": recommendations,
        "recovery_authorized": False,
        "human_approval_required": True,
    }
