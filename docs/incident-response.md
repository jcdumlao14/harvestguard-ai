# Incident Response

## Lifecycle

Alert received
-> authenticate and validate
-> check allowlist and duplicate suppression
-> investigate using bounded read-only evidence
-> persist incident
-> assess impact and confidence
-> request human approval when eligible
-> record approval decision
-> execute the fixed nonproduction simulation
-> verify the simulation result
-> audit the simulation outcome; escalate if execution or verification fails.

## Alert ingestion

The Alertmanager webhook accepts only configured alert names and requires bearer-token authentication.

Firing notifications are subject to duplicate suppression and cooldown. Resolved or non-firing notifications are observed without initiating recovery.

Resolved notifications are not correlated with existing incidents and do not automatically update or close their lifecycle state. A resolved alert alone is not proof of independently verified service recovery.

A policy decision to escalate does not prove that an external notification was delivered or that a human acknowledged the incident.

## Evidence collection

The investigation component queries fixed internal sources:

- API health endpoint.
- Prometheus API target availability.
- Prometheus HTTP 5xx metric.
- Prometheus API latency metric.
- Grafana Tempo trace search.

Collection is read-only and bounded by configured timeouts, response-size limits, and trace-result limits. The component does not accept alert-supplied URLs or arbitrary queries.

Investigation status is:

- `complete`: all configured evidence sources returned available evidence.
- `partial`: at least one source returned available evidence, but not all.
- `unavailable`: no configured source returned available evidence.

Only complete investigations can qualify for the current approval workflow.

Do not attach secrets, credentials, or unrestricted customer records to diagnostic evidence or an LLM prompt.

## Incident assessment

Assessment is deterministic and based on structured evidence. It records severity, symptoms, evidence summaries, likely causes, confidence, and recommendations.

An evidence-supported assessment does not itself authorize recovery. The assessment retains `recovery_authorized=false` and `human_approval_required=true`.

Incomplete or unsupported evidence must be escalated rather than used to justify an action.

## Human approval

The operator requests approval through the internal on-call API. The requester and approver must be different authenticated identities.

The current approval policy fixes:

- Action: `simulate_health_recovery`.
- Environment: `nonproduction`.
- Approval lifetime: 900 seconds.
- Execution: one-time approval consumption.

The API does not accept client-selected recovery actions, environments, identities, or execution adapters.

Rejected, expired, missing, or already consumed approvals cannot authorize execution.

## Recovery boundary

The current recovery implementation is a simulation only. It does not restart services or containers, modify application data, clear caches, execute shell commands, or perform external infrastructure operations.

A successful simulation verifies only the simulated adapter's result. It does not establish that a real service has recovered.

Real service remediation and production recovery are not implemented.

## Failure and escalation

Stop and escalate when:

- Authentication or approval configuration is unavailable.
- Evidence is incomplete or unavailable.
- An incident fails the evidence eligibility requirements.
- The requester and approver are the same identity.
- Approval is rejected, expired, missing, or consumed.
- The action or environment does not match the fixed policy.
- Simulation execution or verification fails.

Do not retry beyond the defined control policy or attempt an alternative action.

## Audit record

The approval and recovery workflow records relevant incident identifiers, action and environment, requester and approver decisions, timestamps, execution state, and sanitized outcomes.

Audit records must not contain credentials, bearer tokens, or unrestricted business records.

## Testing

Use synthetic incidents and mocked telemetry clients for automated tests. Negative tests must cover invalid authentication, unknown alerts, missing evidence, incomplete investigations, rejected approvals, self-approval, expiry, one-time consumption, invalid action or environment, execution failure, and unsuccessful simulation verification.

Tests must not restart real services or modify Docker volumes.
