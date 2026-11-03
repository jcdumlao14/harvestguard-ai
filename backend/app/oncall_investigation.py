"""Bounded, read-only operational evidence collection for on-call incidents.

This module does not execute recovery actions, access business records,
or accept arbitrary URLs or Prometheus queries from alert payloads.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .oncall_contracts import ALLOWED_ALERTS


REQUEST_TIMEOUT_SECONDS = 3.0
MAX_RESPONSE_BYTES = 64 * 1024
INVESTIGATION_WINDOW_MINUTES = 15
MAX_TEMPO_TRACES = 5

# Fixed internal service endpoints. These are not supplied by alert payloads.
API_HEALTH_URL = "http://api:8001/health"
PROMETHEUS_QUERY_URL = "http://prometheus:9090/api/v1/query"
TEMPO_SEARCH_URL = "http://tempo:3200/api/search"

# Only these predefined PromQL expressions can be submitted.
PROMETHEUS_QUERIES = {
    "target_up": 'up{job="harvestguard-api"}',
    "http_5xx_percent": (
        '100 * sum(rate(harvestguard_http_requests_total'
        '{status=~"5.."}[5m])) / '
        'clamp_min(sum(rate(harvestguard_http_requests_total[5m])), 1e-9)'
    ),
    "http_p95_latency": (
        'histogram_quantile(0.95, '
        'sum(rate(harvestguard_http_request_duration_seconds_bucket'
        '[5m])) by (le))'
    ),
}

_TRACE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


class InvestigationError(Exception):
    """Raised when an investigation request cannot be safely performed."""


def _bounded_json_get(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GET a JSON response while enforcing a strict body-size limit."""

    chunks: list[bytes] = []
    total_bytes = 0

    with client.stream(
        "GET",
        url,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as response:
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_RESPONSE_BYTES:
                    raise InvestigationError("Response exceeded size limit")
            except ValueError:
                raise InvestigationError("Invalid response size header")

        for chunk in response.iter_bytes():
            total_bytes += len(chunk)
            if total_bytes > MAX_RESPONSE_BYTES:
                raise InvestigationError("Response exceeded size limit")
            chunks.append(chunk)

    try:
        result = json.loads(b"".join(chunks))
    except (ValueError, UnicodeDecodeError):
        raise InvestigationError("Invalid JSON response")

    if not isinstance(result, dict):
        raise InvestigationError("Unexpected JSON response structure")

    return result


def _unavailable(source: str, reason: str) -> dict[str, Any]:
    """Return a sanitized unavailable-source record."""

    return {
        "source": source,
        "status": "unavailable",
        "reason": reason,
    }


def _collect_health(client: httpx.Client) -> dict[str, Any]:
    try:
        payload = _bounded_json_get(client, API_HEALTH_URL)

        status = payload.get("status")
        service = payload.get("service")

        if not isinstance(status, str):
            return _unavailable("api_health", "Missing health status")

        return {
            "source": "api_health",
            "status": "available",
            "health_status": status[:40],
            "service": service[:80] if isinstance(service, str) else None,
            "scope_note": (
                "The API health endpoint does not independently verify "
                "database health."
            ),
        }
    except Exception as exc:
        return _unavailable("api_health", type(exc).__name__)


def _collect_prometheus(
    client: httpx.Client,
    metric_name: str,
    promql: str,
) -> dict[str, Any]:
    try:
        payload = _bounded_json_get(
            client,
            PROMETHEUS_QUERY_URL,
            params={"query": promql},
        )

        if payload.get("status") != "success":
            return _unavailable(
                f"prometheus_{metric_name}",
                "Prometheus query was not successful",
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            return _unavailable(
                f"prometheus_{metric_name}",
                "Missing query result",
            )

        results = data.get("result")
        if not isinstance(results, list):
            return _unavailable(
                f"prometheus_{metric_name}",
                "Invalid query result",
            )

        # Keep only numeric sample values. Do not return arbitrary labels.
        samples: list[dict[str, str]] = []

        for item in results[:10]:
            if not isinstance(item, dict):
                continue

            value = item.get("value")
            if (
                isinstance(value, list)
                and len(value) >= 2
                and isinstance(value[1], (str, int, float))
            ):
                samples.append({"value": str(value[1])[:40]})

        return {
            "source": f"prometheus_{metric_name}",
            "status": "available",
            "result_count": len(results),
            "samples": samples,
        }

    except Exception as exc:
        return _unavailable(
            f"prometheus_{metric_name}",
            type(exc).__name__,
        )


def _collect_tempo(
    client: httpx.Client,
    now: datetime,
) -> dict[str, Any]:
    try:
        end = now
        start = end - timedelta(minutes=INVESTIGATION_WINDOW_MINUTES)

        # Fixed service filter and bounded time window.
        params = {
            "q": '{ resource.service.name = "harvestguard-api" }',
            "start": str(int(start.timestamp())),
            "end": str(int(end.timestamp())),
            "limit": str(MAX_TEMPO_TRACES),
        }

        payload = _bounded_json_get(
            client,
            TEMPO_SEARCH_URL,
            params=params,
        )

        traces = payload.get("traces")
        if not isinstance(traces, list):
            return _unavailable("tempo", "Invalid trace search response")

        trace_ids: list[str] = []

        for trace in traces[:MAX_TEMPO_TRACES]:
            if not isinstance(trace, dict):
                continue

            trace_id = trace.get("traceID")
            if (
                isinstance(trace_id, str)
                and _TRACE_ID_PATTERN.fullmatch(trace_id)
            ):
                trace_ids.append(trace_id)

        return {
            "source": "tempo",
            "status": "available",
            "window_minutes": INVESTIGATION_WINDOW_MINUTES,
            "trace_count": len(trace_ids),
            "trace_ids": trace_ids,
        }

    except Exception as exc:
        return _unavailable("tempo", type(exc).__name__)


def investigate_alert(
    alert_name: str,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect bounded read-only evidence for one allowlisted alert."""

    if alert_name not in ALLOWED_ALERTS:
        raise ValueError("Alert is not allowlisted")

    timestamp = now or datetime.now(timezone.utc)

    if timestamp.tzinfo is None:
        raise ValueError("Investigation timestamp must include a timezone")

    owns_client = client is None

    if owns_client:
        client = httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
        )

    assert client is not None

    try:
        evidence = [_collect_health(client)]

        for metric_name, promql in PROMETHEUS_QUERIES.items():
            evidence.append(
                _collect_prometheus(client, metric_name, promql)
            )

        evidence.append(_collect_tempo(client, timestamp))

    finally:
        if owns_client:
            client.close()

    available = sum(
        item["status"] == "available" for item in evidence
    )

    overall_status = (
        "complete" if available == len(evidence)
        else "partial" if available > 0
        else "unavailable"
    )

    return {
        "alert": alert_name,
        "investigation_status": overall_status,
        "collected_at": timestamp.astimezone(timezone.utc).isoformat(),
        "evidence": evidence,
        "execution_authority": "read_only",
        "recovery_executed": False,
    }
