# Responder Agent Safety Policy

## Allowed behavior

- Receive authenticated, allowlisted Alertmanager notifications.
- Read fixed, approved health endpoints and sanitized telemetry.
- Collect bounded Prometheus and Tempo evidence.
- Persist necessary incident evidence.
- Evaluate predefined deterministic assessment rules.
- Recommend actions without granting execution authority.
- Request explicit human approval for the fixed nonproduction simulation.
- Record approval decisions and audit events.
- Execute only the fixed simulation after valid approval.
- Verify the simulation result and escalate when it fails.

## Forbidden behavior

- Arbitrary shell execution.
- Model-generated SQL or arbitrary database queries.
- Reading, printing, or exposing secrets.
- Unrestricted access to business records.
- Deleting or rewriting business records.
- Deleting Docker volumes.
- Restarting real services or containers.
- Clearing real application caches.
- Changing production configuration.
- Disabling alerts to hide an incident.
- Automatic approval or self-approval.
- Production deployment or production remediation.
- Selecting an action or execution adapter from untrusted client input.
- Reporting real service recovery based on a simulated result.

## Human approval boundary

The requester and approver must be separately authenticated identities.

The current approval policy permits only:

- Action: `simulate_health_recovery`.
- Environment: `nonproduction`.
- Approval lifetime: 900 seconds.
- One-time execution after approval.

Approval is not inferred from an alert, assessment, LLM response, or recommendation.

## Simulation boundary

The current recovery adapter is a simulation. It does not invoke Docker, execute shell commands, modify databases, clear caches, or perform external infrastructure operations.

Simulation verification confirms only the simulated adapter's expected result. It is not an independent health check of a real external service.

## Isolated recovery-test boundary

The isolated recovery-test harness uses a separate nonproduction service, independent health verifier, and SQLite audit store. Its successful verification applies only to that test service.

The harness is not integrated with the production on-call incident lifecycle and cannot authorize production recovery, bypass human approval, or establish that a production service has recovered.

## Fail-safe behavior

If authentication, evidence, approval, execution, or verification is missing or invalid:

1. Do not execute an alternative action.
2. Do not bypass the approval workflow.
3. Do not retry outside the configured control policy.
4. Record a sanitized audit outcome when possible.
5. Escalate for human review.

Incomplete evidence, denied permissions, unknown actions, expired approvals, and failed simulation verification must fail closed.

## LLM boundary

An optional LLM may summarize redacted evidence or propose a diagnosis.

It cannot grant permissions, approve an action, select an unrestricted execution target, execute arbitrary code, or bypass the deterministic action allowlist.
