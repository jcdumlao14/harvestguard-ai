# Agent Instructions — HarvestGuard AI

## Project goal

Build HarvestGuard AI as one coherent, testable full-stack application.
Read `README.md` and the relevant documentation under `docs/` before changing
code.

## Source of truth

- Product requirements: `docs/specification.md`
- Acceptance criteria: `docs/acceptance-criteria.md`
- Architecture: `docs/architecture.md`
- Development workflow: `docs/development-process.md`
- Agent responsibilities: `docs/agents/team.md`
- Test strategy: `docs/testing.md`
- Deployment: `docs/deployment.md`
- Rollback: `docs/rollback.md`
- Observability: `docs/observability.md`
- Incident response: `docs/incident-response.md`
- Issue plan: `docs/issues/issue-plan.md`

GitHub Issues and pull requests must link implementation work to acceptance
criteria. If a requirement changes, update the specification and its evidence.

## Mandatory workflow

1. Inspect the repository and current Git status before editing.
2. Identify the GitHub Issue and acceptance criteria for the task.
3. Propose a small, bounded implementation plan.
4. Implement only the agreed scope.
5. Add or update tests for changed behavior.
6. Run relevant checks and report their actual results.
7. Review the diff for unintended changes and secrets.
8. Link the pull request to its Issue.
9. Never claim a test, deployment, alert, or remediation succeeded without
   observable evidence.

## Safety rules

- Do not delete user files, reset branches, force-push, or overwrite unrelated
  work without explicit approval.
- Never expose secrets in source code, logs, traces, screenshots, or reports.
- Never use real customer or business data in test fixtures.
- Use database migrations for schema changes.
- Do not make destructive production changes automatically.
- The responder agent must use an explicit allowlist of recovery actions.
- Do not execute arbitrary model-generated shell commands or SQL.
- Require approval for production changes and high-risk remediation.
- Verify recovery through a real health or user-journey check.

## Quality requirements

- Use type hints and input validation in Python.
- Keep API schemas and frontend contracts consistent.
- Prefer small functions and clear error handling.
- Add regression tests for defects.
- Make tests deterministic and independent of production services.
- Do not reduce test coverage or weaken assertions merely to pass CI.
- Keep documentation in English.

## Completion report

For every task, report:
- Files changed
- Acceptance criteria addressed
- Commands actually run
- Test results and failures
- Security or migration considerations
- Remaining work
- Commit SHA or pull request URL, if one exists
