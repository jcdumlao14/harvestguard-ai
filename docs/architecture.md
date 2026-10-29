# Architecture — HarvestGuard AI

## Planned components

- React + TypeScript frontend
- FastAPI backend
- PostgreSQL persistence
- Versioned database migrations
- Automated unit, frontend, and integration tests
- Docker Compose for local development
- GitHub Actions for CI and controlled CD
- OpenTelemetry instrumentation
- Prometheus metrics and Alertmanager rules
- Grafana dashboards; Loki and Tempo where resources permit
- Separate bounded incident responder

## Request flow

Browser -> frontend -> FastAPI -> PostgreSQL

The backend returns validated API responses. A request correlation or trace ID
must be propagated into structured logs and distributed traces. Metrics must
use bounded-cardinality labels and must not include customer identifiers.

## Incident flow

User-impact metric -> alert rule -> incident event -> evidence collection ->
policy evaluation -> allowlisted action -> independent recovery check ->
incident audit.

The alert and responder must not depend on the failed operation being healthy.
The responder should be separately testable and should fail safely if telemetry
or its control plane is unavailable.

## Data boundaries

- Business records belong in PostgreSQL, not telemetry labels.
- Credentials belong in environment-specific secret stores.
- Test fixtures use synthetic data.
- Incident records store only necessary diagnostic evidence.
- The LLM, if enabled, receives redacted, bounded evidence and cannot authorize
  an action outside the deterministic policy layer.

## Local and hosted environments

Docker Compose is the reference development environment. Hosted deployment
must use managed environment secrets, migrations, health checks, and an
explicit release identity.

This document describes the intended architecture, not a deployed system.
