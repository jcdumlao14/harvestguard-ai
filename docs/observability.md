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
