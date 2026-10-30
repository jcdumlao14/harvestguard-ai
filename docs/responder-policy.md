# HarvestGuard AI - Alert Responder Policy

## Purpose

This document describes the current Alertmanager webhook
and its permitted behavior.

The current responder evaluates and escalates alerts.
It is not an autonomous service-repair agent.

## Webhook

Endpoint:

`POST /internal/alerts/alertmanager`

Authentication:

- Bearer token authentication.
- Token is read from `HARVESTGUARD_RESPONDER_TOKEN`.
- Missing authentication is rejected.
- Missing authentication configuration fails closed.

## Approved alert names

- HarvestGuardApiUnavailable
- HarvestGuardPrometheusTargetMissing
- HarvestGuardHighHttp5xxRate
- HarvestGuardHighApiLatency

Unknown alert names must not trigger escalation.

## Current behavior

The responder:

- Evaluates firing notifications.
- Observes resolved notifications.
- Rejects unknown alert names.
- Logs escalation decisions for approved alerts.
- Applies in-memory duplicate suppression and cooldown.
- Uses a default cooldown of 300 seconds and minimum of 30 seconds.

## Meaning of escalation

`decision=escalate` records a policy decision.

It does not prove that an external notification was delivered,
a human acknowledged the incident, or a service was repaired.

## Prohibited current actions

The webhook does not:

- Execute arbitrary shell commands.
- Restart containers.
- Modify database records.
- Delete Docker volumes.
- Change application configuration.
- Perform autonomous production remediation.

## Evidence to retain

- Prometheus alert rules.
- Alertmanager routing configuration.
- Authenticated webhook test.
- Unauthenticated request rejection.
- Unknown alert rejection.
- Approved firing alert log.
- Duplicate suppression test.
- Resolved alert handling.

## Future remediation requirements

Before automated remediation is enabled:

1. Define a narrow action allowlist.
2. Apply least-privilege permissions.
3. Add human approval for high-impact operations.
4. Add timeouts and retry limits.
5. Record every action and result.
6. Test failure and rollback scenarios.
7. Provide a manual disable mechanism.

## Current status

Implemented: authenticated alert evaluation and escalation.

Not implemented: autonomous remediation.
