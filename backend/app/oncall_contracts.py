"""Shared, fixed contracts for HarvestGuard on-call processing."""

ALLOWED_ALERTS = frozenset({
    "HarvestGuardApiUnavailable",
    "HarvestGuardPrometheusTargetMissing",
    "HarvestGuardHighHttp5xxRate",
    "HarvestGuardHighApiLatency",
})
