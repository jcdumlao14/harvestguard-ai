# Architecture — HarvestGuard AI

## Implemented application components

- React + TypeScript frontend.
- FastAPI backend.
- PostgreSQL persistence.
- Docker Compose local development configuration.
- Backend automated tests and frontend production build.
- GitHub Actions CI for backend tests and frontend build.
- OpenTelemetry instrumentation dependencies.
- Prometheus metrics and Alertmanager integration.
- Grafana dashboards and Grafana Tempo tracing.
- Bounded, deterministic on-call responder.
- SQLite-backed incident, approval, and audit state store.

## Application request flow

Browser -> React frontend -> FastAPI -> PostgreSQL.

The backend validates API requests and returns structured responses. Request correlation and tracing should use bounded-cardinality telemetry. Customer identifiers, credentials, and unrestricted business records must not be exposed through telemetry labels.

## Controlled incident flow

Alertmanager notification
-> authenticated webhook
-> alert allowlist and duplicate suppression
-> bounded read-only investigation
-> incident evidence persistence
-> deterministic assessment
-> human approval request
-> separate approver decision
-> fixed nonproduction recovery simulation
-> simulation verification and audit.

The webhook and investigation stages do not receive authority to execute recovery actions.

Approval is a separate operator-initiated workflow through the internal on-call API. It is not an automatic continuation of the Alertmanager webhook request.

## On-call implementation stages

### Stage 1 — Alert ingestion

The webhook authenticates Alertmanager notifications, validates the payload, checks the shared alert allowlist, observes non-firing notifications, and suppresses duplicate firing alerts using a cooldown.

### Stage 2 — Read-only investigation

The investigation component uses fixed internal health, Prometheus, and Tempo endpoints. Requests have bounded timeouts and response sizes. Redirects are disabled, and alert-supplied URLs or queries are not used.

Evidence collection reports `complete`, `partial`, or `unavailable`. An incomplete investigation is not eligible for approval.

### Stage 3 — Incident assessment

The assessment component applies deterministic rules to structured evidence. It records severity, symptoms, evidence summaries, likely causes, confidence, and recommendations.

Assessment does not authorize recovery. The assessment explicitly requires human approval and retains `recovery_authorized=false`.

### Stage 4 — Human approval

The internal on-call API authenticates the operator and approver separately. The requester cannot approve their own request. Approval requests use a fixed action, fixed nonproduction environment, bounded expiry, and auditable decisions.

Approval consumption is one-time. Rejected, expired, missing, or previously consumed approvals cannot authorize execution.

### Stage 5 — Controlled recovery simulation

The current adapter implements only the fixed `simulate_health_recovery` action in `nonproduction`. It returns a simulated result and verifies that result.

The simulation does not invoke Docker, shell commands, SQL, external service controls, or production infrastructure. Simulation verification must not be described as independent verification of a real service recovery.

## Isolated recovery-test harness

Stage 6 provides a separate, nonproduction recovery-test harness. Its test service starts in a degraded state, and a dedicated runner invokes a fixed recovery adapter before performing a fresh health check through a separate HTTP client.

The harness maintains its own SQLite incident and audit-event records. Its service, verification lifecycle, and records are isolated from the production on-call incident and approval stores.

The successful Stage 6 test demonstrates recovery and independent health verification of the isolated test service only. It does not establish production recovery, authorize production remediation, or automatically close a production on-call incident.

## On-call API routes

- `POST /internal/alerts/alertmanager`
- `POST /internal/oncall/incidents/{incident_id}/approvals`
- `POST /internal/oncall/approvals/{approval_id}/decision`
- `POST /internal/oncall/approvals/{approval_id}/execute`
- `GET /internal/oncall/approvals/{approval_id}/audit`

The webhook and approval API use separately configured authentication identities and tokens.

## Data and security boundaries

- Business records belong in PostgreSQL, not telemetry labels.
- Credentials belong in environment-specific secret stores.
- Test fixtures use synthetic data.
- Incident records retain bounded diagnostic evidence.
- Approval and audit records retain the minimum information required to explain decisions and execution outcomes.
- The optional LLM, if enabled, may summarize redacted evidence or propose a diagnosis. It cannot authorize an action or bypass deterministic policy.
- No arbitrary shell execution or model-generated SQL is permitted.
- No unrestricted business-record access is permitted.
- Production remediation and automatic approval are prohibited.

## Local and hosted environments

Docker Compose is the reference local development environment. Local CI and build verification do not prove that the entire stack is currently running.

Public deployment has intentionally been deferred. No public production URL or production recovery capability is claimed.

## Verification status

The on-call regression tests, full backend test suite, application import and OpenAPI route checks, and frontend production build have passed in the local development environment.

These results establish tested implementation behavior, not public deployment or real-world recovery verification.
