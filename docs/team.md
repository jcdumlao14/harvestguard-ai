# HarvestGuard AI - Team and Responsibility Model

## Project ownership

HarvestGuard AI is an independently developed project.
This document describes functional responsibilities and does
not imply that additional people or agents have been deployed.

## Functional responsibilities

| Area | Responsibility |
|---|---|
| Project ownership | Product direction, requirements, prioritization |
| Application engineering | React frontend and FastAPI backend |
| Data engineering | PostgreSQL, inventory and waste records |
| Quality assurance | Automated tests and regression verification |
| Platform engineering | Docker Compose and runtime configuration |
| Observability | Prometheus, Grafana, Tempo and structured logs |
| Incident response | Alert evaluation, escalation and human review |

## Architecture

- React and Vite frontend
- FastAPI backend
- PostgreSQL database
- Docker Compose
- Prometheus
- Grafana
- Alertmanager
- Tempo

## Engineering principles

1. Preserve user and inventory data.
2. Verify changes with tests and runtime evidence.
3. Use deterministic policies for safety-sensitive actions.
4. Separate alert escalation from automated remediation.
5. Document limitations honestly.
6. Do not claim unverified deployment or agent capabilities.

## Future development

Additional agents or contributors require documented roles,
permissions, interfaces, and acceptance tests.

Any remediation agent must use least-privilege access,
an explicit allowlist, audit logging, and human approval
for high-impact operations.
