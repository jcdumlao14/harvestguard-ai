# HarvestGuard AI

**Smart Food Waste Prevention & Inventory Intelligence**

HarvestGuard AI is a specification-driven full-stack application for small
food businesses to manage perishable inventory, record food waste, understand
waste costs, and receive actionable inventory recommendations.

The project also demonstrates production-engineering practices: automated
testing, containerization, CI/CD, rollback, observability, user-impact
alerting, and a bounded on-call responder agent.

## Problem

Small food businesses may lack accessible tools to understand perishable
inventory, expiry risk, waste patterns, and the reliability of the systems
they use to manage stock.

## Planned features

- Inventory and stock movement management
- Expiry and low-stock indicators
- Food waste records and cost analysis
- Dashboard calculations derived from persisted data
- Documented REST API
- Automated tests and Docker Compose
- CI/CD with a rollback procedure
- Correlated metrics, logs, and traces
- User-impact alerting
- Auditable incident response with allowlisted remediation

## Status

Phase 1: specification and repository planning.

No application feature should be described as implemented until its acceptance
criteria have been verified with evidence.

## Technology

- React, TypeScript, and Vite
- Python and FastAPI
- PostgreSQL
- pytest, Vitest, and React Testing Library
- Docker Compose and GitHub Actions
- Prometheus, Grafana, and OpenTelemetry

Final versions and deployment providers will be selected after checking
compatibility, account availability, and current free-tier limitations.

## Local development

The final single-command startup procedure will be documented after the
application and Compose configuration are implemented.

## Documentation

- [Product specification](docs/specification.md)
- [Architecture](docs/architecture.md)
- [Acceptance criteria](docs/acceptance-criteria.md)
- [Agent team](docs/agents/team.md)
- [Development process](docs/development-process.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Rollback](docs/rollback.md)
- [Observability](docs/observability.md)
- [Incident response](docs/incident-response.md)
- [GitHub Issues plan](docs/issues/issue-plan.md)

## Responsible use

Use synthetic data for demonstrations. Never commit credentials, API keys,
production data, or unnecessary personal information. The responder agent
must use explicitly permitted actions and verify recovery independently.
