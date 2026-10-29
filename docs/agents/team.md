# Agent Team and Responsibilities

## Human project owner
Owns scope, approves architecture changes, reviews security-sensitive work,
and authorizes production deployment.

## Product Planning Agent
Maintains specifications, acceptance criteria, task dependencies, and issue
quality. Cannot mark a feature complete without evidence.

## Full-Stack Development Agent
Implements UI, API, database migrations, and tests within the assigned Issue.
Cannot independently authorize production deployment.

## QA and Release Agent
Runs independent tests, reviews regression risk, validates deployment checks,
and verifies rollback procedures.

## On-Call Responder Agent
Collects bounded diagnostic evidence, evaluates deterministic policies,
executes explicitly allowlisted remediation actions, verifies recovery, and
records outcomes. It cannot execute arbitrary shell commands or arbitrary SQL.

## Handoffs
The planning role defines the task. Development supplies code and test results.
QA independently checks the acceptance criteria. The human owner approves
sensitive changes. The responder operates only within its separate incident
policy and permissions.

## Evidence
Record actual tools used, task references, review decisions, test results, and
incident drill outcomes. Do not invent agent activity or claim unsupported
multi-agent orchestration.
