from datetime import datetime, timezone

import httpx
import pytest

from app.oncall_investigation import (
    API_HEALTH_URL,
    MAX_RESPONSE_BYTES,
    PROMETHEUS_QUERIES,
    PROMETHEUS_QUERY_URL,
    TEMPO_SEARCH_URL,
    investigate_alert,
)


FIXED_NOW = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
ALERT = "HarvestGuardApiUnavailable"


def successful_handler(request: httpx.Request) -> httpx.Response:
    if request.url == httpx.URL(API_HEALTH_URL):
        return httpx.Response(
            200,
            json={"status": "ok", "service": "harvestguard-api"},
        )

    if request.url.path == "/api/v1/query":
        query = request.url.params.get("query")
        assert query in PROMETHEUS_QUERIES.values()

        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {"metric": {}, "value": [1, "1"]}
                    ],
                },
            },
        )

    if request.url.path == "/api/search":
        return httpx.Response(
            200,
            json={
                "traces": [
                    {"traceID": "a" * 32},
                    {"traceID": "invalid-trace-id"},
                ]
            },
        )

    return httpx.Response(404)


def make_client(handler=successful_handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_investigation_collects_sanitized_evidence():
    with make_client() as client:
        result = investigate_alert(ALERT, client=client, now=FIXED_NOW)

    assert result["alert"] == ALERT
    assert result["investigation_status"] == "complete"
    assert result["execution_authority"] == "read_only"
    assert result["recovery_executed"] is False

    assert len(result["evidence"]) == 5

    health = result["evidence"][0]
    assert health["health_status"] == "ok"
    assert "scope_note" in health

    tempo = result["evidence"][-1]
    assert tempo["trace_count"] == 1
    assert tempo["trace_ids"] == ["a" * 32]

    # Raw Prometheus labels and raw monitoring payloads are not returned.
    for item in result["evidence"]:
        assert "metric" not in item
        assert "raw_response" not in item


def test_unknown_alert_is_rejected_before_http_request():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    with make_client(handler) as client:
        with pytest.raises(ValueError, match="not allowlisted"):
            investigate_alert("UnknownAlert", client=client, now=FIXED_NOW)

    assert called is False


def test_api_unavailable_does_not_stop_other_evidence_collection():
    def handler(request):
        if request.url == httpx.URL(API_HEALTH_URL):
            return httpx.Response(503)

        return successful_handler(request)

    with make_client(handler) as client:
        result = investigate_alert(ALERT, client=client, now=FIXED_NOW)

    assert result["investigation_status"] == "partial"
    assert result["evidence"][0]["status"] == "unavailable"
    assert result["evidence"][1]["status"] == "available"


def test_monitoring_sources_can_be_unavailable_without_crashing():
    def handler(request):
        return httpx.Response(503)

    with make_client(handler) as client:
        result = investigate_alert(ALERT, client=client, now=FIXED_NOW)

    assert result["investigation_status"] == "unavailable"
    assert all(
        item["status"] == "unavailable"
        for item in result["evidence"]
    )


def test_oversized_response_is_rejected():
    def handler(request):
        if request.url == httpx.URL(API_HEALTH_URL):
            return httpx.Response(
                200,
                content=b"x" * (MAX_RESPONSE_BYTES + 1),
            )

        return successful_handler(request)

    with make_client(handler) as client:
        result = investigate_alert(ALERT, client=client, now=FIXED_NOW)

    assert result["evidence"][0]["status"] == "unavailable"
    assert result["evidence"][0]["reason"] == "InvestigationError"


def test_invalid_tempo_trace_ids_are_not_returned():
    def handler(request):
        if request.url.path == "/api/search":
            return httpx.Response(
                200,
                json={
                    "traces": [
                        {"traceID": "not-a-trace-id"},
                        {"traceID": "b" * 32},
                    ]
                },
            )

        return successful_handler(request)

    with make_client(handler) as client:
        result = investigate_alert(ALERT, client=client, now=FIXED_NOW)

    tempo = result["evidence"][-1]
    assert tempo["trace_ids"] == ["b" * 32]


def test_naive_timestamp_is_rejected():
    with make_client() as client:
        with pytest.raises(ValueError, match="timezone"):
            investigate_alert(
                ALERT,
                client=client,
                now=datetime(2026, 11, 3, 8, 0),
            )


def test_alert_payload_cannot_supply_prometheus_query():
    captured_queries = []

    def handler(request):
        if request.url.path == "/api/v1/query":
            captured_queries.append(request.url.params["query"])

        return successful_handler(request)

    with make_client(handler) as client:
        investigate_alert(ALERT, client=client, now=FIXED_NOW)

    assert len(captured_queries) == 3
    assert set(captured_queries) == set(PROMETHEUS_QUERIES.values())

def test_5xx_query_reports_percentage_not_raw_rate():
    query = PROMETHEUS_QUERIES["http_5xx_percent"]

    assert query.startswith("100 * sum(rate(")
    assert '{status=~"5.."}[5m]' in query
    assert (
        "clamp_min(sum(rate(harvestguard_http_requests_total[5m])), 1e-9)"
        in query
    )
    assert "http_5xx_rate" not in PROMETHEUS_QUERIES
