# HarvestGuard AI — Alert Responder Policy

## Purpose

This document defines the implemented Alertmanager webhook, read-only investigation, deterministic incident assessment, human approval workflow, and nonproduction recovery simulation.

The responder is bounded and fail-closed. It is not an autonomous production repair agent.

## Webhook

Endpoint:

`POST /internal/alerts/alertmanager`

Authentication:

- Bearer-token authentication.
- Token is read from `HARVESTGUARD_RESPONDER_TOKEN`.
- Missing authentication is rejected.
- Missing authentication configuration fails closed.

## Approved alert names

- `HarvestGuardApiUnavailable`
- `HarvestGuardPrometheusTargetMissing`
- `HarvestGuardHighHttp5xxRate`
- `HarvestGuardHighApiLatency`

Unknown alert names must not trigger investigation, approval, or recovery.

## Implemented alert behavior

The webhook:

- Validates Alertmanager notifications.
- Evaluates firing notifications.
- Observes non-firing or resolved notifications without correlating or closing existing incidents.
- Rejects unknown alert names.
- Applies in-memory duplicate suppression and cooldown.
- Keeps duplicate-suppression state in process memory; it is not durable across application restarts.
- Uses a default cooldown of 300 seconds and a minimum of 30 seconds.
- Starts bounded read-only investigation for accepted firing alerts.
- Applies deterministic incident assessment.
- Persists incident evidence and assessment.
- Releases the duplicate-suppression entry if incident persistence fails.

A policy decision to escalate does not prove that an external notification was delivered, that a human acknowledged the incident, or that a service was repaired.

## Read-only investigation

The investigation component accesses fixed internal API health, Prometheus, and Tempo endpoints.

It uses bounded timeouts, response sizes, and trace-result limits. Redirects are disabled. Alert-supplied URLs and arbitrary Prometheus queries are not accepted.

Investigation status is `complete`, `partial`, or `unavailable`. Only a complete investigation can qualify for the current approval workflow.

## Deterministic assessment

The assessment records severity, symptoms, evidence summaries, likely causes, confidence, and recommendations.

Assessment does not authorize recovery. It requires human approval and retains `recovery_authorized=false`.

## Approval API

The internal approval API uses separately configured operator and approver credentials:

- `HARVESTGUARD_ONCALL_OPERATOR_TOKEN`
- `HARVESTGUARD_ONCALL_OPERATOR_ID`
- `HARVESTGUARD_ONCALL_APPROVER_TOKEN`
- `HARVESTGUARD_ONCALL_APPROVER_ID`

The requester and approver must be different identities. Identity values are derived from server-side configuration, not client-supplied request fields.

The current fixed policy is:

- Action: `simulate_health_recovery`.
- Environment: `nonproduction`.
- Approval lifetime: 900 seconds.
- Approval consumption: one time only.

The API requires a complete investigation, evidence-supported assessment, `human_approval_required=true`, and `recovery_authorized=false`.

## Recovery boundary

The only permitted action is the fixed nonproduction simulation. The API invokes the default simulated adapter; clients cannot supply an adapter.

The simulation does not restart containers, execute shell commands, modify databases, clear caches, or call external service controls.

Simulation verification is not real service recovery verification. Production remediation is not implemented.

## Prohibited behavior

The responder must not:

- Execute arbitrary shell commands.
- Execute model-generated SQL.
- Restart containers or services.
- Delete or modify business records.
- Delete Docker volumes.
- Read, print, or disclose secrets.
- Change application configuration as a recovery action.
- Perform autonomous production remediation.
- Bypass human approval or the deterministic action allowlist.
- Report actual service recovery based only on a simulation result.

## Evidence and audit

Incident, approval, and audit state must contain only necessary diagnostic and authorization information.

Never store bearer tokens, credentials, or unrestricted customer records in incident evidence or audit events.

## Current implementation status

Implemented and locally tested:

- Authenticated Alertmanager webhook.
- Alert allowlisting and duplicate suppression.
- Bounded read-only investigation.
- Deterministic incident assessment.
- Incident persistence.
- Separate authenticated human approval.
- Expiry, one-time consumption, and audit events.
- Fixed nonproduction recovery simulation and simulation verification.

Not implemented:

- Autonomous service remediation.
- Real service or container restart.
- Production recovery.
- Public production deployment.
- External notification delivery guarantees.
