# HarvestGuard AI - Prioritized Completion Plan

## Priority 1 - CI and evidence

- Obtain a successful GitHub Actions run.
- Preserve backend test results.
- Preserve frontend production build evidence.
- Retain API and PostgreSQL persistence evidence.
- Keep architecture and specification documents synchronized.

## Priority 2 - Product and agent evidence

- Compare acceptance criteria with implemented behavior.
- Document actual context-management behavior.
- Define agent responsibilities and permissions.
- Do not claim undeployed agents.

## Priority 3 - Alerting

- Retain Prometheus alert rules.
- Verify Alertmanager routing and authentication.
- Preserve approved and rejected webhook test evidence.
- Distinguish escalation from external notification delivery.

## Priority 4 - Deployment

- Decide whether local containerized operation is sufficient.
- If production deployment is required, document hosting,
  configuration, health checks and rollback.
- Do not claim production deployment without verification.

## Priority 5 - Safe remediation

- Define approved remediation actions.
- Use least-privilege permissions.
- Require approval for high-impact operations.
- Add execution logs, timeouts and rollback.
- Test the remediation executor before enabling it.

## GitHub issue snapshot

- #5 4 3 2 1: [Phase 6] Full test suite and rubric evidence [Phase 4] Safe on-call agent and verified remediation [Phase 4] Authenticated Alertmanager webhook and cooldown [Phase 3] OpenTelemetry and correlated structured logs [Phase 2] Public task tracker and agent execution evidence [OPEN OPEN OPEN OPEN OPEN] https://github.com/jcdumlao14/harvestguard-ai/issues/5 https://github.com/jcdumlao14/harvestguard-ai/issues/4 https://github.com/jcdumlao14/harvestguard-ai/issues/3 https://github.com/jcdumlao14/harvestguard-ai/issues/2 https://github.com/jcdumlao14/harvestguard-ai/issues/1

## Completion policy

A rubric criterion is complete only when supported by
implementation evidence, test output, or verified runtime behavior.

Documentation alone does not prove implementation.

No Git changes are committed or pushed by this script.
