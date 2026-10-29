# Deployment Plan

## Local reference environment
Use Docker Compose for the frontend, API, PostgreSQL, and local observability
services. Keep local development independent of hosted provider availability.

## Candidate hosted providers
- GitHub Actions for CI.
- Render for a public frontend/API demonstration.
- Supabase Free PostgreSQL, subject to current limits and availability.
- Local Prometheus and Grafana for repeatable observability demonstrations.

Verify current plans, regions, connectivity, secret handling, database
suspension policies, usage quotas, and provider terms before provisioning.

## Free-tier caveats
Free web services may sleep or restart. Free databases may pause, expire, lack
backups, or have limited capacity. Never present a free demonstration setup
as a production SLA.

## Release prerequisites
- CI passes.
- Required secrets are configured outside the repository.
- Database migrations are reviewed and tested.
- Health checks and smoke tests pass.
- The release artifact or commit is identifiable.
- Rollback steps and compatible database changes are understood.

## Deployment evidence
Record public URLs, commit SHA, deployment timestamp, smoke-test output, and
known limitations. Do not commit credentials or deployment tokens.
