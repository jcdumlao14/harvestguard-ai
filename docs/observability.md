# Observability and User-Impact Alerting

## Primary user journey
Create or update an inventory item and confirm the persisted result.

## Signals
- Metrics: request count, error ratio, latency, and user-journey success.
- Structured logs: severity, operation, result, release, and trace ID.
- Traces: inbound request, application work, and database spans where supported.

## Privacy
Do not record passwords, tokens, connection strings, full request bodies, or
unnecessary personal or business data. Avoid high-cardinality labels such as
trace IDs, user IDs, and item IDs in Prometheus metrics.

## Initial alert
Create a reproducible alert for elevated failure rate or sustained latency
on the primary user journey. Choose a threshold after measuring the normal
test workload; document the evaluation window and minimum sample count.

## Incident verification
Trigger the rule using a controlled fault. Confirm that the alert fires,
evidence can be correlated, the responder is invoked, and recovery is checked.

## UI and evidence
Use Grafana for dashboards. Add log and trace backends as resource limits allow.
Record dashboard screenshots and alert test results without exposing secrets.

## Local Tempo and authenticated alert delivery

Integration date: 2026-10-30.

- Grafana Tempo is deployed as a local Compose service.
- OTLP/HTTP traces are received on the internal Tempo port 4318.
- Tempo query/readiness API is exposed on local port 3200.
- The API exports traces to `http://tempo:4318/v1/traces`.
- Grafana provisions the Tempo datasource using UID `tempo`.
- Tempo uses a separate persistent `tempo_data` volume.
- Alertmanager sends alerts to the internal API webhook.
- Alertmanager reads its bearer credential from a read-only mounted local secret.
- The API reads the matching credential from the ignored local `.env` file.
- A synthetic allowlisted alert is used for local delivery verification.
- The responder records/escalates incidents only.
- No shell executor, container restart executor, or database mutation executor is enabled.
- The webhook cooldown is in-process and must be replaced with shared state for multi-replica deployment.

See `docs/tempo-alerting-execution-evidence.md` for execution results.
