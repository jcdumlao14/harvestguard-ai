# Responder Agent Safety Policy

## Allowed behavior
- Read approved health endpoints and sanitized telemetry.
- Retrieve relevant incident and release metadata.
- Evaluate predefined deterministic rules.
- Execute specifically configured, reversible remediation actions.
- Run independent verification checks.
- Record an audit entry and escalate when recovery fails.

## Forbidden behavior
- Arbitrary shell execution or model-generated SQL.
- Deleting or rewriting business records.
- Reading or printing secrets.
- Disabling alerts to hide an incident.
- Deploying to production without human approval.
- Reporting recovery without a successful verification check.

## Fail-safe behavior
If evidence is incomplete, permissions are denied, the action is unknown, or
verification fails, stop automatic remediation and escalate.

## LLM boundary
An optional LLM may summarize redacted evidence or propose a diagnosis. It does
not grant permissions and cannot bypass the deterministic action allowlist.
