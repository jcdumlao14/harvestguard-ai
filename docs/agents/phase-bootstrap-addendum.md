# Agent workflow addendum

Before changing code, read README.md and the relevant modular documents:
`docs/specification.md`, `docs/acceptance-criteria.md`,
`docs/development-process.md`, `docs/agents/team.md`,
`docs/agents/responder-policy.md`, `docs/testing.md`,
`docs/observability.md`, `docs/incident-response.md`, and `docs/rollback.md`.

Work against a defined GitHub Issue and acceptance criteria. Preserve existing
business data. Use reviewed database migrations for schema changes. Never make
destructive production changes automatically. Never execute arbitrary
model-generated shell commands or SQL. The responder may select only explicit
allowlisted actions. Production changes and high-risk remediation require
human approval. Verify recovery independently through a real health or
user-journey check. Record actual files, commands, test outcomes, risks,
remaining work, and real commit/PR references. Do not invent agent activity.

Review this addendum from AGENTS.md; the existing AGENTS.md is intentionally
left unchanged by the bootstrap to preserve project-specific instructions.
