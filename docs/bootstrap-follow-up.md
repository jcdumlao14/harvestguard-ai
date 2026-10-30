# Phase 1-6 bootstrap: required verification and remaining work

This bootstrap adds infrastructure scaffolding. It does not prove deployment,
telemetry correlation, alert delivery, or autonomous incident recovery.

1. Run backend tests and frontend build after installing the new Alembic dependency.
2. Validate the Alembic initial migration against a fresh disposable database.
   Do not point it at the existing SQLite database or production without a
   reviewed migration plan and backup. Existing SQLite demo data is preserved.
3. Add Prometheus instrumentation and a tested `/metrics` endpoint; Compose
   currently contains the scrape configuration but the API endpoint is not yet
   implemented.
4. Add OpenTelemetry traces and structured request logs with a shared trace ID;
   verify no secrets or unnecessary customer/business data enter telemetry.
5. Configure Grafana data sources and dashboards, then perform a controlled
   non-production alert drill. Alertmanager currently has no external receiver.
6. Integrate responder with alert intake, an incident audit store, bounded
   action adapters, timeouts, idempotency, and independent health/user-journey
   verification. The included policy only authorizes action names; it executes
   nothing and cannot run shell commands or SQL.
7. Add authentication and authorization before exposing business endpoints
   publicly. Do not deploy real inventory data before this is complete.
8. Configure provider-specific dev deployment and protected manual production
   promotion. The included deployment workflow intentionally fails closed.
9. Create/link public GitHub Issues and attach actual CI, deployment, alert,
   recovery-drill, commit, and PR evidence. Do not fabricate agent activity.

Useful local commands:
- `docker compose config`
- `docker compose up --build`
- `docker compose ps`
- `docker compose logs --tail=100`
- `docker compose down` (preserves named volumes)

Never use `docker compose down -v` casually: it deletes local named volumes.
