# Incident Response

## Lifecycle
Alert -> acknowledge -> collect evidence -> classify -> select permitted action
-> execute -> verify -> resolve or escalate.

## Evidence collection
Gather alert identity, time window, affected operation, sanitized error counts,
latency, trace IDs, and release metadata. Do not attach secrets or full customer
records to an LLM prompt.

## Policy
The responder can select only actions declared in a reviewed allowlist.
Every action must have defined preconditions, timeout, idempotency expectations,
risk classification, and a verification method.

## Recovery
A successful action is not proof of recovery. Run an independent health or
user-journey check. If verification fails, stop retries at the configured
limit and escalate to the human operator.

## Audit record
Store incident ID, triggering alert, timestamps, evidence references, selected
action, authorization result, verification result, and final disposition.

## Testing
Use a controlled fault in a non-production environment. Include negative tests
for unknown actions, missing evidence, timeouts, denied permissions, and
unsuccessful recovery.
